'use client'
import { useEffect, useRef } from 'react'

export default function ThreeScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    let animId: number
    const canvas = canvasRef.current
    if (!canvas) return

    const loadThree = async () => {
      const THREE = await import('three')

      const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
      renderer.setPixelRatio(window.devicePixelRatio)
      renderer.setClearColor(0x000000, 0)

      const scene = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(60, canvas.clientWidth / canvas.clientHeight, 0.1, 100)
      camera.position.z = 4

      // Main icosahedron
      const geo = new THREE.IcosahedronGeometry(1.4, 1)
      const mat = new THREE.MeshPhongMaterial({
        color: 0x38bdf8,
        emissive: 0x0369a1,
        shininess: 100,
        transparent: true,
        opacity: 0.85,
      })
      const mesh = new THREE.Mesh(geo, mat)
      scene.add(mesh)

      // Wireframe overlay
      const wireMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.15 })
      const wireMesh = new THREE.Mesh(new THREE.IcosahedronGeometry(1.45, 1), wireMat)
      scene.add(wireMesh)

      // Lights
      const ambient = new THREE.AmbientLight(0xffffff, 0.4)
      scene.add(ambient)
      const point1 = new THREE.PointLight(0x38bdf8, 3, 20)
      point1.position.set(5, 5, 5)
      scene.add(point1)
      const point2 = new THREE.PointLight(0x818cf8, 1.5, 20)
      point2.position.set(-5, -5, -5)
      scene.add(point2)

      // Stars
      const starGeo = new THREE.BufferGeometry()
      const starCount = 600
      const positions = new Float32Array(starCount * 3)
      for (let i = 0; i < starCount * 3; i++) positions[i] = (Math.random() - 0.5) * 60
      starGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      const stars = new THREE.Points(
        starGeo,
        new THREE.PointsMaterial({ color: 0xffffff, size: 0.08, transparent: true, opacity: 0.6 })
      )
      scene.add(stars)

      const resize = () => {
        if (!canvas) return
        const w = canvas.clientWidth
        const h = canvas.clientHeight
        renderer.setSize(w, h, false)
        camera.aspect = w / h
        camera.updateProjectionMatrix()
      }
      resize()
      window.addEventListener('resize', resize)

      let t = 0
      const animate = () => {
        animId = requestAnimationFrame(animate)
        t += 0.01
        mesh.rotation.x = t * 0.3
        mesh.rotation.y = t * 0.5
        wireMesh.rotation.x = t * 0.3
        wireMesh.rotation.y = t * 0.5
        mesh.position.y = Math.sin(t * 0.8) * 0.15
        wireMesh.position.y = mesh.position.y
        stars.rotation.y = t * 0.02
        renderer.render(scene, camera)
      }
      animate()

      return () => {
        window.removeEventListener('resize', resize)
        cancelAnimationFrame(animId)
        renderer.dispose()
      }
    }

    let cleanup: (() => void) | undefined
    loadThree().then(fn => { cleanup = fn })

    return () => {
      cleanup?.()
      cancelAnimationFrame(animId)
    }
  }, [])

  return <canvas ref={canvasRef} className="w-full h-full" />
}
