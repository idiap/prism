// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import * as os from 'os'
import * as readline from 'readline'
import * as fs from 'fs'
import { spawn, ChildProcessWithoutNullStreams } from 'child_process'
import * as vscode from 'vscode'

import {
  PrismIdeCheckResult,
  PrismIdeHealthResponse,
  PrismIdeRunResult,
} from '../infoview-api/protocol'
import { PrismLogger } from './logger'

interface PendingRequest {
  resolve: (value: unknown) => void
  reject: (error: Error) => void
  timeout: NodeJS.Timeout
}

interface RpcEnvelope<T> {
  id: number | null
  ok: boolean
  result?: T
  error?: {
    message: string
    traceback?: string
  }
}

export type PrismAvailability =
  | { status: 'ok' }
  | { status: 'python-missing'; pythonPath: string }
  | { status: 'prism-missing'; pythonPath: string; detail: string }

export class PrismSessionClient implements vscode.Disposable {
  private static readonly REQUEST_TIMEOUT_MS = 60000
  private process?: ChildProcessWithoutNullStreams
  private nextId = 1
  private readonly pending = new Map<number, PendingRequest>()

  constructor(private readonly logger: PrismLogger) {}

  dispose() {
    for (const [, pending] of this.pending) {
      clearTimeout(pending.timeout)
      pending.reject(new Error('PRISM IDE session client disposed'))
    }
    this.pending.clear()
    this.process?.kill()
    this.process = undefined
  }

  async health(workspaceFolder: vscode.WorkspaceFolder): Promise<PrismIdeHealthResponse> {
    return this.request<PrismIdeHealthResponse>(workspaceFolder, 'health', {})
  }

  async checkAvailability(workspaceFolder: vscode.WorkspaceFolder): Promise<PrismAvailability> {
    const { pythonPath, cwd, env } = this.buildSpawnContext(workspaceFolder)
    return new Promise<PrismAvailability>(resolve => {
      const probe = spawn(pythonPath, ['-c', 'import prism; import prism.tooling.ide_server'], { cwd, env })
      let stderr = ''
      probe.stderr.on('data', (chunk: Buffer) => {
        stderr += chunk.toString()
      })
      probe.on('error', (error: NodeJS.ErrnoException) => {
        if (error.code === 'ENOENT') {
          resolve({ status: 'python-missing', pythonPath })
        } else {
          resolve({ status: 'prism-missing', pythonPath, detail: error.message })
        }
      })
      probe.on('exit', code => {
        if (code === 0) {
          resolve({ status: 'ok' })
        } else {
          resolve({ status: 'prism-missing', pythonPath, detail: stderr.trim() })
        }
      })
    })
  }

  async checkDocument(
    workspaceFolder: vscode.WorkspaceFolder,
    documentPath: string,
    documentText: string,
  ): Promise<PrismIdeCheckResult> {
    return this.request<PrismIdeCheckResult>(workspaceFolder, 'checkDocument', {
      document_path: documentPath,
      document_text: documentText,
    })
  }

  async runDocument(
    workspaceFolder: vscode.WorkspaceFolder,
    documentPath: string,
    documentText: string,
    backendName: 'fake' | 'litellm',
    model?: string,
  ): Promise<PrismIdeRunResult> {
    return this.request<PrismIdeRunResult>(
      workspaceFolder,
      'runDocument',
      {
        document_path: documentPath,
        document_text: documentText,
        backend_name: backendName,
        model,
      },
      this.executionTimeoutMs(),
    )
  }

  async latestRunForDocument(
    workspaceFolder: vscode.WorkspaceFolder,
    documentPath: string,
  ): Promise<PrismIdeRunResult | null> {
    return this.request<PrismIdeRunResult | null>(workspaceFolder, 'latestRunForDocument', {
      document_path: documentPath,
    })
  }

  async runsForDocument(
    workspaceFolder: vscode.WorkspaceFolder,
    documentPath: string,
  ): Promise<PrismIdeRunResult[]> {
    return this.request<PrismIdeRunResult[]>(workspaceFolder, 'runsForDocument', {
      document_path: documentPath,
    })
  }

  async deleteRunForDocument(
    workspaceFolder: vscode.WorkspaceFolder,
    documentPath: string,
    runId: string,
  ): Promise<boolean> {
    return this.request<boolean>(workspaceFolder, 'deleteRunForDocument', {
      document_path: documentPath,
      run_id: runId,
    })
  }

  private executionTimeoutMs(): number {
    const seconds = Number(vscode.workspace.getConfiguration('prismSolver').get('execution.timeoutSeconds', 900))
    if (!Number.isFinite(seconds) || seconds <= 0) {
      return PrismSessionClient.REQUEST_TIMEOUT_MS
    }
    return seconds * 1000
  }

  private async request<T>(
    workspaceFolder: vscode.WorkspaceFolder,
    method: string,
    params: Record<string, unknown>,
    timeoutMs: number = PrismSessionClient.REQUEST_TIMEOUT_MS,
  ): Promise<T> {
    const child = await this.ensureProcess(workspaceFolder)
    const id = this.nextId++
    const payload = JSON.stringify({ id, method, params })
    this.logger.trace('session.request', 'Sending request to PRISM IDE backend.', { method, id })

    return new Promise<T>((resolve, reject) => {
      const rejectRequest = (error: Error) => {
        const pending = this.pending.get(id)
        if (!pending) {
          return
        }
        clearTimeout(pending.timeout)
        this.pending.delete(id)
        if (this.process === child && !this.isProcessWritable(child)) {
          this.process = undefined
        }
        pending.reject(error)
      }
      const timeout = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`PRISM IDE backend timed out after ${timeoutMs}ms for ${method}`))
      }, timeoutMs)
      this.pending.set(id, { resolve: value => resolve(value as T), reject, timeout })
      if (!this.isProcessWritable(child)) {
        rejectRequest(this.backendUnavailableError(method))
        return
      }
      try {
        child.stdin.write(payload + os.EOL, error => {
          if (error) {
            rejectRequest(this.backendWriteError(method, error))
          }
        })
      } catch (error) {
        rejectRequest(this.backendWriteError(method, error))
      }
    })
  }

  private async ensureProcess(workspaceFolder: vscode.WorkspaceFolder): Promise<ChildProcessWithoutNullStreams> {
    if (this.process && this.isProcessWritable(this.process)) {
      return this.process
    }
    this.process = undefined
    const { pythonPath, cwd, env } = this.buildSpawnContext(workspaceFolder)
    this.logger.info('session.spawn', 'Launching PRISM IDE backend.', { pythonPath, cwd })
    const child = spawn(pythonPath, ['-m', 'prism.tooling.ide_server'], {
      cwd,
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    this.process = child
    let stderr = ''

    readline.createInterface({ input: child.stdout }).on('line', line => this.handleLine(line))
    child.stderr.on('data', (chunk: Buffer) => {
      const text = chunk.toString()
      stderr = `${stderr}${text}`.slice(-4000)
      this.logger.warnOnce(`stderr:${text}`, 'session.stderr', 'PRISM IDE backend wrote to stderr.', { text })
    })
    child.on('error', error => this.failAll(error instanceof Error ? error : new Error(String(error))))
    child.on('exit', code => {
      const detail = stderr.trim()
      const error = new Error(
        detail
          ? `PRISM IDE backend exited with code ${code ?? 'unknown'}: ${detail}`
          : `PRISM IDE backend exited with code ${code ?? 'unknown'}`,
      )
      this.process = undefined
      if (this.pending.size) {
        this.failAll(error)
      }
    })
    return child
  }

  private handleLine(line: string) {
    let envelope: RpcEnvelope<unknown>
    try {
      envelope = JSON.parse(line) as RpcEnvelope<unknown>
    } catch (error) {
      this.logger.warn('session.invalidJson', 'Ignored non-JSON backend output.', { line })
      return
    }
    if (typeof envelope.id !== 'number') {
      return
    }
    const pending = this.pending.get(envelope.id)
    if (!pending) {
      return
    }
    clearTimeout(pending.timeout)
    this.pending.delete(envelope.id)
    if (envelope.ok) {
      pending.resolve(envelope.result)
    } else {
      const message = envelope.error?.message || 'PRISM IDE backend request failed'
      pending.reject(new Error(envelope.error?.traceback ? `${message}\n${envelope.error.traceback}` : message))
    }
  }

  private failAll(error: Error) {
    for (const [, pending] of this.pending) {
      clearTimeout(pending.timeout)
      pending.reject(error)
    }
    this.pending.clear()
    this.process = undefined
  }

  private isProcessWritable(child: ChildProcessWithoutNullStreams): boolean {
    return child.exitCode === null
      && child.signalCode === null
      && !child.killed
      && child.stdin.writable
      && !child.stdin.destroyed
      && !child.stdin.writableEnded
  }

  private backendUnavailableError(method: string): Error {
    return new Error(`PRISM IDE backend is not available while sending ${method}. See the PRISM Solver Debug log for backend startup errors.`)
  }

  private backendWriteError(method: string, error: unknown): Error {
    const message = error instanceof Error ? error.message : String(error)
    return new Error(`Failed to send ${method} to the PRISM IDE backend: ${message}`)
  }

  private buildSpawnContext(workspaceFolder: vscode.WorkspaceFolder): { pythonPath: string; cwd: string; env: NodeJS.ProcessEnv } {
    const cwd = workspaceFolder.uri.fsPath
    const configuredPythonPath = String(vscode.workspace.getConfiguration('prismSolver').get('pythonPath', 'python')).trim()
    const pythonPath = this.resolvePythonPath(configuredPythonPath, cwd)
    return {
      pythonPath,
      cwd,
      env: {
        ...process.env,
        PYTHONPATH: this.pythonPath(cwd),
      },
    }
  }

  private resolvePythonPath(configuredPythonPath: string, cwd: string): string {
    if (configuredPythonPath && configuredPythonPath !== 'python') {
      return configuredPythonPath
    }
    const venvPythonPath = process.platform === 'win32'
      ? `${cwd}\\.venv\\Scripts\\python.exe`
      : `${cwd}/.venv/bin/python`
    return fs.existsSync(venvPythonPath) ? venvPythonPath : (configuredPythonPath || 'python')
  }

  private pythonPath(cwd: string): string {
    const existing = process.env.PYTHONPATH
    const srcPath = `${cwd}/src`
    return existing ? `${srcPath}${pathSeparator()}${existing}` : srcPath
  }
}

function pathSeparator(): string {
  return process.platform === 'win32' ? ';' : ':'
}
