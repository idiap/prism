// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import * as vscode from 'vscode'

import { PrismIdeRunResult } from '../infoview-api/protocol'

export type PrismRunPanelNode =
  | { kind: 'status'; label: string; detail?: string }
  | { kind: 'runSelector'; selectedRun?: PrismIdeRunResult }
  | { kind: 'runOption'; run: PrismIdeRunResult; selected: boolean }
  | { kind: 'field'; label: string; value: unknown; description?: string; children: PrismRunPanelNode[] }

export class PrismRunTreeProvider implements vscode.TreeDataProvider<PrismRunPanelNode> {
  private readonly onDidChangeTreeDataEmitter = new vscode.EventEmitter<PrismRunPanelNode | undefined>()
  readonly onDidChangeTreeData = this.onDidChangeTreeDataEmitter.event
  private run?: PrismIdeRunResult
  private runs: PrismIdeRunResult[] = []
  private selectedRunId?: string
  private statusMessage?: string

  refresh(run?: PrismIdeRunResult, runs: PrismIdeRunResult[] = [], selectedRunId?: string, statusMessage?: string) {
    this.run = run
    this.runs = runs
    this.selectedRunId = selectedRunId
    this.statusMessage = statusMessage
    this.onDidChangeTreeDataEmitter.fire(undefined)
  }

  getTreeItem(element: PrismRunPanelNode): vscode.TreeItem {
    if (element.kind === 'status') {
      const item = new vscode.TreeItem(element.label, vscode.TreeItemCollapsibleState.None)
      item.description = element.detail
      item.iconPath = new vscode.ThemeIcon('info')
      return item
    }
    if (element.kind === 'runSelector') {
      const item = new vscode.TreeItem('Run', vscode.TreeItemCollapsibleState.Expanded)
      item.description = element.selectedRun ? this.runLabel(element.selectedRun) : undefined
      item.tooltip = 'Select a persisted PRISM run for this file'
      item.iconPath = new vscode.ThemeIcon('history')
      return item
    }
    if (element.kind === 'runOption') {
      const item = new vscode.TreeItem(this.runLabel(element.run), vscode.TreeItemCollapsibleState.None)
      item.id = element.run.run_id ?? element.run.run_path ?? this.runLabel(element.run)
      item.description = this.runDescription(element.run, element.selected)
      item.tooltip = this.runTooltip(element.run)
      item.iconPath = new vscode.ThemeIcon(element.selected ? 'check' : 'circle-outline')
      item.contextValue = 'prismRunOption'
      if (element.run.run_id) {
        item.command = {
          command: 'prismSolver.selectRun',
          title: 'Select PRISM Run',
          arguments: [element.run.run_id],
        }
      }
      return item
    }
    if (element.kind === 'field') {
      const collapsible = element.children.length
        ? vscode.TreeItemCollapsibleState.Collapsed
        : vscode.TreeItemCollapsibleState.None
      const item = new vscode.TreeItem(element.label, collapsible)
      item.description = element.description ?? this.valueDescription(element.value)
      item.tooltip = this.fieldTooltip(element.label, element.value)
      item.iconPath = new vscode.ThemeIcon(this.fieldIcon(element.value))
      return item
    }
    return new vscode.TreeItem('Unknown PRISM output', vscode.TreeItemCollapsibleState.None)
  }

  getChildren(element?: PrismRunPanelNode): vscode.ProviderResult<PrismRunPanelNode[]> {
    if (!element) {
      if (!this.run) {
        return [{ kind: 'status', label: this.statusMessage || 'Run a .prism file to populate the Run Explorer.' }]
      }
      const selector = this.runSelectorNodes()
      if (!this.run.output) {
        return [
          ...selector,
          { kind: 'status', label: this.run.message || 'No run output.', detail: this.run.status },
        ]
      }
      return [
        ...selector,
        this.fieldNode('status', this.run.output.status),
        this.fieldNode('result', this.run.output.result),
        this.fieldNode('trace', this.arrayField(this.run.output.trace)),
        this.fieldNode('diagnostics', this.arrayField(this.run.output.diagnostics)),
        this.fieldNode('effect_records', this.run.output.effect_records ?? {}),
        this.fieldNode('metadata', this.run.output.metadata ?? {}),
        this.fieldNode('program', {
          path: this.run.output.path ?? null,
          source_hash: this.run.output.source_hash,
          trace_version: this.run.output.trace_version,
        }),
      ]
    }
    if (element.kind === 'runSelector') {
      return this.runs.map(run => ({
        kind: 'runOption' as const,
        run,
        selected: Boolean(run.run_id && run.run_id === this.selectedRunId),
      }))
    }
    if (element.kind === 'field') {
      return element.children
    }
    return []
  }

  private runSelectorNodes(): PrismRunPanelNode[] {
    if (this.runs.length <= 1) {
      return []
    }
    return [{ kind: 'runSelector', selectedRun: this.run }]
  }

  private fieldNode(label: string, value: unknown): PrismRunPanelNode {
    return {
      kind: 'field',
      label,
      value,
      description: this.valueDescription(value),
      children: this.fieldChildren(value),
    }
  }

  private arrayField<T>(value: T[] | undefined | null): T[] {
    return Array.isArray(value) ? value : []
  }

  private fieldChildren(value: unknown): PrismRunPanelNode[] {
    if (Array.isArray(value)) {
      return value.map((item, index) => this.fieldNode(this.arrayItemLabel(item, index), item))
    }
    if (this.isRecord(value)) {
      return Object.entries(value).map(([key, item]) => this.fieldNode(key, item))
    }
    return []
  }

  private arrayItemLabel(value: unknown, index: number): string {
    if (this.isRecord(value)) {
      const ref = this.stringField(value, 'ref')
      if (ref) {
        return `[${index}] ${ref}`
      }
      const key = this.stringField(value, 'key')
      if (key) {
        return `[${index}] ${key}`
      }
      const text = this.stringField(value, 'text')
      if (text) {
        return `[${index}] ${this.truncate(text, 40)}`
      }
    }
    return `[${index}]`
  }

  private fieldIcon(value: unknown): string {
    if (Array.isArray(value)) {
      return 'list-tree'
    }
    if (this.isRecord(value)) {
      return 'json'
    }
    return 'symbol-field'
  }

  private valueDescription(value: unknown): string | undefined {
    if (Array.isArray(value)) {
      return `${value.length} item${value.length === 1 ? '' : 's'}`
    }
    if (this.isRecord(value)) {
      return `${Object.keys(value).length} field${Object.keys(value).length === 1 ? '' : 's'}`
    }
    if (typeof value === 'string') {
      return this.truncate(value, 96)
    }
    if (value === null || value === undefined) {
      return String(value)
    }
    return String(value)
  }

  private fieldTooltip(label: string, value: unknown): vscode.MarkdownString {
    const markdown = new vscode.MarkdownString(undefined, true)
    markdown.appendMarkdown(`**${this.escapeMarkdown(label)}**`)
    markdown.appendCodeblock(this.stringifyValue(value), 'json')
    return markdown
  }

  private stringifyValue(value: unknown): string {
    if (typeof value === 'string') {
      return value
    }
    try {
      return JSON.stringify(value, null, 2) ?? String(value)
    } catch {
      return String(value)
    }
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value)
  }

  private stringField(value: Record<string, unknown>, key: string): string | undefined {
    const field = value[key]
    return typeof field === 'string' && field ? field : undefined
  }

  private truncate(value: string, length: number): string {
    if (value.length <= length) {
      return value
    }
    return `${value.slice(0, Math.max(length - 3, 0))}...`
  }

  private runLabel(run: PrismIdeRunResult): string {
    return run.run_created_at || run.run_id || 'Persisted run'
  }

  private runDescription(run: PrismIdeRunResult, selected: boolean): string {
    const backend = run.model ? `${run.backend} ${run.model}` : run.backend
    return selected ? `${backend} · selected` : `${backend} · ${run.status}`
  }

  private runTooltip(run: PrismIdeRunResult): vscode.MarkdownString {
    const markdown = new vscode.MarkdownString(undefined, true)
    markdown.appendMarkdown(`**${this.escapeMarkdown(this.runLabel(run))}**`)
    markdown.appendMarkdown(`\n\nStatus: \`${run.status}\``)
    markdown.appendMarkdown(`\n\nBackend: \`${run.model ? `${run.backend} ${run.model}` : run.backend}\``)
    if (run.run_id) {
      markdown.appendMarkdown(`\n\nRun id: \`${this.escapeBackticks(run.run_id)}\``)
    }
    if (run.message) {
      markdown.appendMarkdown(`\n\n${this.escapeMarkdown(run.message)}`)
    }
    return markdown
  }

  private escapeMarkdown(value: unknown): string {
    return String(value ?? '').replace(/[\\`*_{}\[\]()#+\-.!|>]/g, '\\$&')
  }

  private escapeBackticks(value: unknown): string {
    return String(value ?? '').replace(/`/g, '\\`')
  }
}
