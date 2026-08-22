export type UserRole = 'ADMIN' | 'USER' | 'VIEWER'
export type DeviceStatus = 'PROVISIONING' | 'ONLINE' | 'OFFLINE' | 'DISABLED' | 'ERROR'
export type ConnectionType = 'WIFI' | 'ETHERNET' | 'CELLULAR' | 'LORA' | 'OTHER'

export type User = { id: string; first_name: string; last_name: string; email: string; role: UserRole }
export type Pagination = { page: number; page_size: number; total_items: number; total_pages: number }
export type Paginated<T> = { items: T[]; pagination: Pagination }
export type Site = { id: string; name: string; description: string | null; latitude: string | null; longitude: string | null; is_active: boolean; created_by_user_id: string; created_at: string; updated_at: string }
export type Device = { id: string; site_id: string; device_uid: string; name: string; description: string | null; device_type: string; manufacturer: string | null; model: string | null; firmware_version: string | null; connection_type: ConnectionType; status: DeviceStatus; is_active: boolean; last_seen_at: string | null; created_at: string; updated_at: string; site: Pick<Site, 'id' | 'name' | 'is_active'> }
export type TokenPair = { access_token: string; refresh_token: string; expires_in: number }
export type ApiErrorBody = { error?: { code: string; message: string; details: Record<string, unknown> } }
