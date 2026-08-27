// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import React, {useCallback, useEffect, useRef, useState} from 'react'
import clsx from 'clsx'
import {translate} from '@docusaurus/Translate'
import {useCodeBlockContext} from '@docusaurus/theme-common/internal'
import Button from '@theme/CodeBlock/Buttons/Button'
import IconCopy from '@theme/Icon/Copy'
import IconSuccess from '@theme/Icon/Success'

import styles from './styles.module.css'

function copyLabel() {
  return translate({
    id: 'theme.CodeBlock.copy',
    message: 'Copy',
    description: 'The copy button label on code blocks',
  })
}

function copiedLabel() {
  return translate({
    id: 'theme.CodeBlock.copied',
    message: 'Copied',
    description: 'The copied button label on code blocks',
  })
}

async function copyToClipboard(text) {
  if (navigator.clipboard) return navigator.clipboard.writeText(text)

  const {default: copy} = await import('copy-text-to-clipboard')
  return copy(text)
}

export default function CopyButton({className}) {
  const {
    metadata: {code},
  } = useCodeBlockContext()
  const [isCopied, setIsCopied] = useState(false)
  const copyTimeout = useRef()
  const label = isCopied ? copiedLabel() : copyLabel()

  const copyCode = useCallback(() => {
    copyToClipboard(code).then(() => {
      setIsCopied(true)
      copyTimeout.current = window.setTimeout(() => setIsCopied(false), 1000)
    })
  }, [code])

  useEffect(() => () => window.clearTimeout(copyTimeout.current), [])

  return (
    <Button
      aria-label={label}
      title={label}
      className={clsx(className, styles.copyButton, isCopied && styles.copyButtonCopied)}
      onClick={copyCode}>
      <span className={styles.copyButtonIcons} aria-hidden="true">
        <IconCopy className={styles.copyButtonIcon} />
        <IconSuccess className={styles.copyButtonSuccessIcon} />
      </span>
      <span className={styles.copyButtonLabel}>{label}</span>
    </Button>
  )
}
