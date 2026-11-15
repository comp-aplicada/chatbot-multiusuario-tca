import { STORAGE_KEY } from '../constants.ts'

export function readSessionId(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function saveSessionId(sessionId: string): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, sessionId)
  } catch {
    return
  }
}

export function clearSessionId(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    return
  }
}
