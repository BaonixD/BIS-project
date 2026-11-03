import { useLocation } from 'react-router'

export function LocationProbe() {
  const location = useLocation()
  return <p data-testid="location">{location.pathname}</p>
}
