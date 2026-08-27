// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

const {prismDarkTheme, prismLightTheme} = require('./src/prism-themes')

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Prism',
  tagline: 'Explicit, typed, and verifiable reasoning',
  favicon: 'img/prism.svg',

  url: 'https://gitlab.idiap.ch',
  baseUrl: '/neurosymbolicai/prism/',
  organizationName: 'neurosymbolicai',
  projectName: 'prism',
  trailingSlash: false,
  onBrokenLinks: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  clientModules: [require.resolve('./src/prism-language.js')],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: require.resolve('./sidebars.js'),
          routeBasePath: 'docs',
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      },
    ],
  ],

  themeConfig: {
    colorMode: {
      defaultMode: 'light',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Prism',
      logo: {
        alt: 'Prism logo',
        src: 'img/prism.svg',
      },
      items: [
        {to: '/docs/installation', label: 'Install', position: 'left'},
        {to: '/docs/quick-start', label: 'Quick start', position: 'left'},
        {
          type: 'docSidebar',
          sidebarId: 'tutorialsSidebar',
          label: 'Tutorials',
          position: 'left',
        },
        {
          type: 'docSidebar',
          sidebarId: 'conceptsSidebar',
          label: 'Concepts',
          position: 'left',
        },
        {
          href: 'https://github.com/idiap/prism',
          label: 'GitLab',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Get started',
          items: [
            {label: 'Installation', to: '/docs/installation'},
            {label: 'Quick start', to: '/docs/quick-start'},
            {label: 'Tutorials', to: '/docs/tutorials'},
          ],
        },
        {
          title: 'Editor',
          items: [
            {label: 'Language support', to: '/docs/editors/vscode-language-support'},
            {label: 'Run Explorer', to: '/docs/editors/vscode-run-explorer'},
          ],
        },
        {
          title: 'Concepts',
          items: [
            {label: 'Concept map', to: '/docs/concepts'},
            {label: 'Language foundations', to: '/docs/concepts/language-foundations'},
            {label: 'Effects and permissions', to: '/docs/concepts/effects-failures-permissions'},
            {label: 'Reasoning types', to: '/docs/concepts/reasoning-types'},
            {label: 'Relations and materialization', to: '/docs/concepts/relations-materialization'},
            {label: 'Workflows', to: '/docs/concepts/workflows'},
            {label: 'Capabilities and integration', to: '/docs/concepts/tools-interop'},
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Idiap Research Institute.`,
    },
    prism: {
      theme: prismLightTheme,
      darkTheme: prismDarkTheme,
    },
  },
}

module.exports = config
