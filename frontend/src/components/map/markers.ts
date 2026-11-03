import { divIcon, icon } from 'leaflet'
import myLocationUrl from '@/assets/icons/my-location.svg'

/** Lucide «car» (Figma Icon/car), white on the black car marker. */
const CAR_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
  '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/>' +
  '<circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/></svg>'

/** Figma Route (4:317): pickup — 22px black circle with an 8px white centre. */
export const pickupIcon = divIcon({
  className: 'map-marker',
  html: '<span class="flex size-[22px] items-center justify-center rounded-full bg-bg-inverse"><span class="size-2 rounded-full bg-bg-canvas"></span></span>',
  iconSize: [22, 22],
  iconAnchor: [11, 11],
})

/** Figma Route (4:317): drop-off — 20px black square with an 8px white centre. */
export const dropoffIcon = divIcon({
  className: 'map-marker',
  html: '<span class="flex size-5 items-center justify-center bg-bg-inverse"><span class="size-2 bg-bg-canvas"></span></span>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
})

/** Figma CarMarker (24:418): 36px black circle, Elevation/Card, white 20px car. */
export const carIcon = divIcon({
  className: 'map-marker',
  html: `<span class="flex size-9 items-center justify-center rounded-full bg-bg-inverse shadow-card">${CAR_SVG}</span>`,
  iconSize: [36, 36],
  iconAnchor: [18, 18],
})

/** Figma MyLocation (4:170): blue dot with a white ring and a 15% halo. */
export const myLocationIcon = icon({
  iconUrl: myLocationUrl,
  iconSize: [56, 56],
  iconAnchor: [28, 28],
  className: 'map-marker',
})
