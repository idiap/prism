// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

'use strict'

const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const readline = require('node:readline')
const { spawn } = require('node:child_process')

class CompilerServiceClient {
  constructor(vscode) {
    this.vscode = vscode
    this.sessions = new Map()
    this.documents = new Map()
  }

  async checkDocument(document) {
    const folder = this.vscode.workspace.getWorkspaceFolder(document.uri)
      || this.vscode.workspace.workspaceFolders?.[0]
    if (!folder || document.uri.scheme !== 'file') return undefined
    const key = document.uri.toString()
    const cached = this.documents.get(key)
    if (cached?.version === document.version) return cached.promise
    const request = this.request(folder, 'checkDocument', {
      document_path: document.uri.fsPath,
      document_text: document.getText(),
    })
    const promise = request.catch(error => {
      if (this.documents.get(key)?.promise === promise) this.documents.delete(key)
      throw error
    })
    this.documents.set(key, { version: document.version, promise })
    return promise
  }

  async definitionAt(document, position) {
    const folder = this.vscode.workspace.getWorkspaceFolder(document.uri)
      || this.vscode.workspace.workspaceFolders?.[0]
    if (!folder || document.uri.scheme !== 'file') return undefined
    return this.request(folder, 'definitionAt', {
      document_path: document.uri.fsPath,
      document_text: document.getText(),
      line: position.line,
      character: position.character,
    })
  }

  async completionAt(document, position) {
    const folder = this.vscode.workspace.getWorkspaceFolder(document.uri)
      || this.vscode.workspace.workspaceFolders?.[0]
    if (!folder || document.uri.scheme !== 'file') return []
    return this.request(folder, 'completionAt', {
      document_path: document.uri.fsPath,
      document_text: document.getText(),
      line: position.line,
      character: position.character,
    })
  }

  forget(document) {
    this.documents.delete(document.uri.toString())
  }

  invalidate() {
    this.documents.clear()
  }

  async request(folder, method, params) {
    const session = this.session(folder)
    const child = await this.ensureProcess(session)
    const id = session.nextId++
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        session.pending.delete(id)
        reject(new Error(`PRISM compiler service timed out while handling ${method}`))
      }, 30000)
      session.pending.set(id, { resolve, reject, timeout })
      child.stdin.write(`${JSON.stringify({ id, method, params })}${os.EOL}`, error => {
        if (!error) return
        clearTimeout(timeout)
        session.pending.delete(id)
        reject(error)
      })
    })
  }

  session(folder) {
    const root = folder.uri.fsPath
    let session = this.sessions.get(root)
    if (!session) {
      session = { root, nextId: 1, pending: new Map(), process: undefined }
      this.sessions.set(root, session)
    }
    return session
  }

  async ensureProcess(session) {
    if (session.process && !session.process.killed && session.process.stdin.writable) {
      return session.process
    }
    const pythonPath = session.pythonPath || await this.resolvePythonPath(session.root)
    session.pythonPath = pythonPath
    const child = spawn(pythonPath, ['-m', 'prism.tooling.ide_server'], {
      cwd: session.root,
      env: process.env,
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    session.process = child
    let stderr = ''
    child.stderr.on('data', chunk => {
      stderr = `${stderr}${chunk}`.slice(-8000)
    })
    readline.createInterface({ input: child.stdout }).on('line', line => {
      let response
      try {
        response = JSON.parse(line)
      } catch {
        return
      }
      const pending = session.pending.get(response.id)
      if (!pending) return
      clearTimeout(pending.timeout)
      session.pending.delete(response.id)
      if (response.ok) pending.resolve(response.result)
      else pending.reject(new Error(response.error?.message || 'PRISM compiler service failed'))
    })
    let stopped = false
    const fail = error => {
      if (stopped || session.process !== child) return
      stopped = true
      session.process = undefined
      for (const pending of session.pending.values()) {
        clearTimeout(pending.timeout)
        pending.reject(error)
      }
      session.pending.clear()
    }
    child.on('error', fail)
    child.on('exit', code => {
      const detail = stderr.trim()
      const suffix = detail ? `: ${detail}` : ''
      fail(new Error(`PRISM compiler service exited with code ${code ?? 'unknown'}${suffix}`))
    })
    return child
  }

  pythonCandidates(root) {
    const configured = this.vscode.workspace
      .getConfiguration('prism.languageServer')
      .get('pythonPath', '')
      .trim()
    if (configured) return [configured]
    const virtualEnvironment = process.platform === 'win32'
      ? path.join(root, '.venv', 'Scripts', 'python.exe')
      : path.join(root, '.venv', 'bin', 'python')
    return fs.existsSync(virtualEnvironment) ? [virtualEnvironment, 'python'] : ['python']
  }

  async resolvePythonPath(root) {
    const failures = []
    for (const candidate of this.pythonCandidates(root)) {
      try {
        await this.probePython(candidate, root)
        return candidate
      } catch (error) {
        failures.push(`${candidate}: ${error instanceof Error ? error.message : String(error)}`)
      }
    }
    throw new Error(
      `PRISM is not available from the selected Python interpreter. ${failures.join('; ')}. `
      + 'Set prism.languageServer.pythonPath to the Python executable in the Prism toolchain environment.',
    )
  }

  probePython(pythonPath, root) {
    return new Promise((resolve, reject) => {
      const probe = spawn(pythonPath, ['-c', 'import prism.tooling.ide_server'], {
        cwd: root,
        env: process.env,
        stdio: ['ignore', 'ignore', 'pipe'],
      })
      let stderr = ''
      let settled = false
      probe.stderr.on('data', chunk => {
        stderr = `${stderr}${chunk}`.slice(-4000)
      })
      probe.on('error', error => {
        if (settled) return
        settled = true
        reject(error)
      })
      probe.on('exit', code => {
        if (settled) return
        settled = true
        if (code === 0) {
          resolve()
          return
        }
        reject(new Error(stderr.trim() || `probe exited with code ${code ?? 'unknown'}`))
      })
    })
  }

  dispose() {
    this.documents.clear()
    for (const session of this.sessions.values()) {
      if (session.process && !session.process.killed) session.process.kill()
      for (const pending of session.pending.values()) {
        clearTimeout(pending.timeout)
        pending.reject(new Error('PRISM compiler service disposed'))
      }
      session.pending.clear()
    }
    this.sessions.clear()
  }
}

module.exports = { CompilerServiceClient }
