// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docsSidebar: [
    'installation',
    'quick-start',
    {
      type: 'category',
      label: 'Tutorials',
      link: {
        type: 'doc',
        id: 'tutorials/overview',
      },
      items: [
        'tutorials/refinement-loop',
      ],
    },
    {
      type: 'category',
      label: 'VS Code',
      items: [
        'editors/vscode-language-support',
        'editors/vscode-run-explorer',
      ],
    },
    {
      type: 'category',
      label: 'Language concepts',
      link: {
        type: 'doc',
        id: 'concepts/overview',
      },
      items: [
        {
          type: 'category',
          label: 'Language foundation',
          items: [
            'concepts/language-foundations',
            'concepts/effects-failures-permissions',
          ],
        },
        {
          type: 'category',
          label: 'Epistemic reasoning',
          items: [
            'concepts/reasoning-types',
            'concepts/relations-materialization',
            'concepts/provenance-types',
            'concepts/assurance-types',
          ],
        },
        {
          type: 'category',
          label: 'Execution',
          items: [
            'concepts/workflows',
            'concepts/execution-tracing',
          ],
        },
        {
          type: 'category',
          label: 'Capabilities and integration',
          items: [
            'concepts/agents',
            'concepts/tools-interop',
            'concepts/sources-connections-resources',
            'concepts/skills',
            'concepts/hooks',
            'concepts/external-artifacts',
          ],
        },
      ],
    },
  ],
  conceptsSidebar: [
    'concepts/overview',
    {
      type: 'category',
      label: 'Language foundation',
      items: [
        'concepts/language-foundations',
        'concepts/effects-failures-permissions',
      ],
    },
    {
      type: 'category',
      label: 'Epistemic reasoning',
      items: [
        'concepts/reasoning-types',
        'concepts/relations-materialization',
        'concepts/provenance-types',
        'concepts/assurance-types',
      ],
    },
    {
      type: 'category',
      label: 'Execution',
      items: [
        'concepts/workflows',
        'concepts/execution-tracing',
      ],
    },
    {
      type: 'category',
      label: 'Capabilities and integration',
      items: [
        'concepts/agents',
        'concepts/tools-interop',
        'concepts/sources-connections-resources',
        'concepts/skills',
        'concepts/hooks',
        'concepts/external-artifacts',
      ],
    },
  ],
  tutorialsSidebar: [
    'tutorials/overview',
    'tutorials/refinement-loop',
  ],
}

module.exports = sidebars
