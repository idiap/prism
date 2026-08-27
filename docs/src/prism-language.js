// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

'use strict'

const {Prism} = require('prism-react-renderer')

const python = Prism.languages.python

// Browser equivalent of the VS Code TextMate grammar and compiler semantic tokens.
Prism.languages.prism = {
  comment: python.comment,
  'triple-quoted-string': {
    pattern: /(?:\b[bBrR])?("""|''')[\s\S]*?\1/,
    greedy: true,
    alias: 'string',
  },
  string: {
    pattern: /(?:\b[bBrR])?(["'])(?:\\.|(?!\1)[^\\\r\n])*\1/,
    greedy: true,
  },
  'effect-name': {
    pattern: /\b(?:File|Data|Network|Process|Tool|MCP|AI|Clock|Random|Trace|Hook)\.(?:Read|Write|Request|Run|Call|Generate|Sample|Emit|Register)\b/,
    alias: 'constant',
  },
  'agent-name': {
    pattern: /(^[\t ]*agent\s+)[A-Za-z_]\w*/m,
    lookbehind: true,
    alias: 'class-name',
  },
  function: [
    {
      pattern: /(^[\t ]*(?:def|reasoning|workflow|tool|theorem|relation)\s+)[A-Za-z_]\w*/m,
      lookbehind: true,
    },
    {
      pattern: /(\bby\s+)[A-Z][A-Za-z0-9_]*/,
      lookbehind: true,
    },
    /\b[A-Za-z_]\w*(?=\s*(?:\[[^\]\r\n]+\]\s*)?\()/,
  ],
  boolean: python.boolean,
  variant: {
    pattern: /(^[\t ]*\|\s*)[A-Z][A-Za-z0-9_]*/m,
    lookbehind: true,
  },
  keyword: [
    {
      pattern: /(^[\t ]*)(?:type|def|reasoning|workflow|tool|theorem|agent|relation)\b/m,
      lookbehind: true,
    },
    /\b(?:return|if|else|match|case|try|solve|execute|using|sequence|parallel|choice|repeat|fails|from|import|as|where|by|forall|exists|and|or|not|on|accept|stop)\b/,
  ],
  label: {
    pattern: /(^[\t ]*\[\s*)[a-z_][A-Za-z0-9_]*(?=\s*:)/m,
    lookbehind: true,
  },
  property: [
    {
      pattern: /(^[\t ]+)[a-z_][A-Za-z0-9_]*(?=\s*:(?!=))/m,
      lookbehind: true,
    },
    {
      pattern: /([,(]\s*)[a-z_][A-Za-z0-9_]*(?=\s*=(?!=))/,
      lookbehind: true,
    },
    /(?<=\.)[a-z_][A-Za-z0-9_]*/,
  ],
  parameter: /\b[a-z_][A-Za-z0-9_]*(?=\s*:(?!=))/,
  variable: {
    pattern: /(^[\t ]*)[a-z_][A-Za-z0-9_]*(?=[^#\r\n]*(?<![=!<>])=(?!=))/m,
    lookbehind: true,
  },
  'class-name': [
    {
      pattern: /(^[\t ]*(?:type|agent)\s+)[A-Za-z_]\w*/m,
      lookbehind: true,
    },
    /\b(?:Bool|Nat|Int|Float|Decimal|Char|String|Bytes|Unit|Never|Time|Duration|Type|Prop|List|Set|Map|Option|Result)\b/,
    /\b(?:Generated|Evidence|Supported|Validated|Proof|Verified)\b/,
    /\b(?:Source|GraphSource|MaterialPolicy|RefinementPolicy|Relation|Workflow|Execution|Trace|Connection|Resource|CoreTerm|ProofSyntax|Claim|Skill|Skills|Tool|Tools|Hooks|Codex|Claude)\b/,
    /\b[A-Z][A-Za-z0-9_]*\b/,
  ],
  builtin: /\b(?:exact|assumption|intro|apply|constructor|cases|induction|rewrite|unfold|simp|decide)\b/,
  number: python.number,
  operator: /\|~|\|-|:=|->|=>|!(?!=)|==|!=|<=|>=|<|>|(?<![=!<>])=(?!=)|\*\*|\/\/|[+\-*/%]/,
  punctuation: /[|{}[\](),.:]/,
}
