export type ErrorDetails = Record<string, unknown>

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: ErrorDetails
  readonly requestId: string | null

  constructor(
    status: number,
    code: string,
    message: string,
    details: ErrorDetails = {},
    requestId: string | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
  }
}

export const NETWORK_ERROR_CODE = 'network_error'
export const UNKNOWN_ERROR_CODE = 'unknown_error'

export function isApiError(error: unknown, code?: string): error is ApiError {
  return error instanceof ApiError && (code === undefined || error.code === code)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function toApiError(body: unknown, response: Response): ApiError {
  const requestId = response.headers.get('X-Request-ID')
  if (isRecord(body) && isRecord(body.error) && typeof body.error.code === 'string') {
    const { code, message, details } = body.error
    return new ApiError(
      response.status,
      code,
      typeof message === 'string' ? message : code,
      isRecord(details) ? details : {},
      typeof body.request_id === 'string' ? body.request_id : requestId,
    )
  }
  return new ApiError(
    response.status,
    UNKNOWN_ERROR_CODE,
    `Unexpected response ${response.status}`,
    {},
    requestId,
  )
}

export function networkError(cause: unknown): ApiError {
  const error = new ApiError(0, NETWORK_ERROR_CODE, 'Network request failed')
  error.cause = cause
  return error
}
