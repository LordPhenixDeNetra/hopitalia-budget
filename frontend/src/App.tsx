import { useState } from 'react'
import { RouterProvider } from 'react-router'
import { Fournisseurs } from './Fournisseurs'
import { creerRouteur } from './routes'

export default function App() {
  const [routeur] = useState(creerRouteur)
  return (
    <Fournisseurs>
      <RouterProvider router={routeur} />
    </Fournisseurs>
  )
}
