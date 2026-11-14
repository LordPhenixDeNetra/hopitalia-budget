import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom ne fournit ni matchMedia ni ResizeObserver, utilisés par Ant Design.
window.matchMedia ??= (requete: string) =>
  ({
    matches: false,
    media: requete,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }) as MediaQueryList

globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

afterEach(cleanup)
