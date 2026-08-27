// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import * as vscode from 'vscode'

type LogLevel = 'off' | 'error' | 'warn' | 'info' | 'debug' | 'trace'

const priorities: Record<LogLevel, number> = {
  off: 0,
  error: 1,
  warn: 2,
  info: 3,
  debug: 4,
  trace: 5,
}

export class PrismLogger implements vscode.Disposable {
  private readonly onceKeys = new Set<string>()
  private level: LogLevel = 'info'
  private includePayloads = false
  private revealOnError = true

  constructor(private readonly channel: vscode.OutputChannel) {
    this.refreshConfiguration()
  }

  refreshConfiguration() {
    const config = vscode.workspace.getConfiguration('prismSolver')
    const configured = String(config.get('logging.level', 'info'))
    this.level = configured in priorities ? (configured as LogLevel) : 'info'
    this.includePayloads = Boolean(config.get('logging.includePayloads', false))
    this.revealOnError = Boolean(config.get('logging.revealOnError', true))
  }

  dispose() {
    this.channel.dispose()
  }

  show(preserveFocus = true) {
    this.channel.show(preserveFocus)
  }

  info(event: string, message: string, data?: unknown) {
    this.log('info', event, message, data)
  }

  debug(event: string, message: string, data?: unknown) {
    this.log('debug', event, message, data)
  }

  trace(event: string, message: string, data?: unknown) {
    this.log('trace', event, message, data)
  }

  warn(event: string, message: string, data?: unknown) {
    this.log('warn', event, message, data)
  }

  warnOnce(key: string, event: string, message: string, data?: unknown) {
    if (this.onceKeys.has(key)) {
      return
    }
    this.onceKeys.add(key)
    this.warn(event, message, data)
  }

  error(event: string, message: string, data?: unknown) {
    this.log('error', event, message, data)
    if (this.revealOnError) {
      this.show(true)
    }
  }

  private log(level: LogLevel, event: string, message: string, data?: unknown) {
    if (priorities[level] > priorities[this.level]) {
      return
    }
    let line = `[${new Date().toISOString()}] [${level.toUpperCase()}] [${event}] ${message}`
    if (data !== undefined) {
      line += this.includePayloads ? ` ${JSON.stringify(data)}` : ` ${this.summarize(data)}`
    }
    this.channel.appendLine(line)
  }

  private summarize(data: unknown): string {
    if (data === null || data === undefined) {
      return String(data)
    }
    if (typeof data === 'string' || typeof data === 'number' || typeof data === 'boolean') {
      return String(data)
    }
    if (data instanceof Error) {
      return data.stack || data.message
    }
    if (Array.isArray(data)) {
      if (data.length === 0) {
        return '[]'
      }
      if (data.length > 5) {
        return `[${data.length} items]`
      }
      return `[${data.map(item => this.summarizeValue(item)).join(', ')}]`
    }
    if (typeof data === 'object') {
      const entries = Object.entries(data)
      if (entries.length === 0) {
        return '{}'
      }
      return entries.map(([key, value]) => `${key}=${this.summarizeValue(value)}`).join(' ')
    }
    return typeof data
  }

  private summarizeValue(value: unknown): string {
    if (value === null || value === undefined) {
      return String(value)
    }
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value)
    }
    if (value instanceof Error) {
      return value.stack || value.message
    }
    if (Array.isArray(value)) {
      return this.summarize(value)
    }
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value)
      } catch {
        return '[object]'
      }
    }
    return typeof value
  }
}
