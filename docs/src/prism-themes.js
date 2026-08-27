// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

'use strict'

const {themes} = require('prism-react-renderer')

function extendTheme(theme, styles) {
  return {...theme, styles: [...theme.styles, ...styles]}
}

const prismLightTheme = extendTheme(themes.github, [
  {types: ['keyword'], style: {color: '#cf222e', fontStyle: 'normal'}},
  {types: ['function'], style: {color: '#8250df'}},
  {types: ['class-name', 'variant'], style: {color: '#0550ae'}},
  {types: ['property'], style: {color: '#116329'}},
  {types: ['parameter'], style: {color: '#953800'}},
  {types: ['label'], style: {color: '#0a7b72'}},
  {types: ['operator'], style: {color: '#cf222e'}},
  {types: ['builtin', 'boolean', 'constant', 'number'], style: {color: '#0550ae'}},
])

const prismDarkTheme = extendTheme(themes.dracula, [
  {types: ['keyword'], style: {color: '#ff79c6', fontStyle: 'normal'}},
  {types: ['function'], style: {color: '#50fa7b'}},
  {types: ['class-name', 'variant'], style: {color: '#4ec9b0'}},
  {types: ['property'], style: {color: '#9cdcfe'}},
  {types: ['parameter'], style: {color: '#ffb86c'}},
  {types: ['label'], style: {color: '#f1fa8c'}},
  {types: ['operator'], style: {color: '#ff79c6'}},
  {types: ['builtin', 'boolean', 'constant', 'number'], style: {color: '#bd93f9'}},
  {types: ['string'], style: {color: '#f1fa8c'}},
])

module.exports = {prismDarkTheme, prismLightTheme}
