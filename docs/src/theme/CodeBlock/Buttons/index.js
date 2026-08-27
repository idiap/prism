// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import React from 'react'
import clsx from 'clsx'
import CopyButton from '@theme/CodeBlock/Buttons/CopyButton'
import WordWrapButton from '@theme/CodeBlock/Buttons/WordWrapButton'

import styles from './styles.module.css'

export default function CodeBlockButtons({className}) {
  return (
    <div className={clsx(className, styles.buttonGroup)}>
      <WordWrapButton />
      <CopyButton />
    </div>
  )
}
