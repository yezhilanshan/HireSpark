export type ClassValue =
    | string
    | number
    | null
    | undefined
    | boolean
    | ClassDictionary
    | ClassArray

interface ClassDictionary {
    [id: string]: unknown
}

interface ClassArray extends Array<ClassValue> {}

function collectClassNames(value: ClassValue, result: string[]) {
    if (!value) {
        return
    }

    if (typeof value === 'string' || typeof value === 'number') {
        result.push(String(value))
        return
    }

    if (Array.isArray(value)) {
        for (const item of value) {
            collectClassNames(item, result)
        }
        return
    }

    if (typeof value === 'object') {
        for (const [key, isEnabled] of Object.entries(value)) {
            if (isEnabled) {
                result.push(key)
            }
        }
    }
}

export function cn(...inputs: ClassValue[]) {
    const result: string[] = []
    for (const input of inputs) {
        collectClassNames(input, result)
    }
    return result.join(' ')
}
