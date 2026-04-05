'use client'
import { useEffect, useRef } from 'react'

export default function ThreeScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    let animId: number
    let disposed = false

    const canvas = canvasRef.current
    if (!canvas) return

    const loadThree = async () => {
      const THREE = await import('three')
      if (disposed || !canvasRef.current) return

      let renderer: InstanceType<typeof THREE.WebGLRenderer>
      try {
        renderer = new THREE.WebGLRenderer({
          canvas,
          antialias: true,
          alpha: true,
          powerPreference: 'default',
          failIfMajorPerformanceCaveat: false,
        })
      } catch {
        return
      }

      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setClearColor(0x000000, 0)

      const scene  = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(60, canvas.clientWidth / (canvas.clientHeight || 1), 0.1, 100)
      camera.position.z = 4

      const geo      = new THREE.IcosahedronGeometry(1.4, 1)
      const mat      = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0369a1, shininess: 100, transparent: true, opacity: 0.85 })
      const mesh     = new THREE.Mesh(geo, mat)
      const wireMat  = new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.15 })
      const wireGeo  = new THREE.IcosahedronGeometry(1.45, 1)
      const wireMesh = new THREE.Mesh(wireGeo, wireMat)
      scene.add(mesh, wireMesh)

      scene.add(new THREE.AmbientLight(0xffffff, 0.4))
      const p1 = new THREE.PointLight(0x38bdf8, 3, 20)
      p1.position.set(5, 5, 5)
      scene.add(p1)
      const p2 = new THREE.PointLight(0x818cf8, 1.5, 20)
      p2.position.set(-5, -5, -5)
      scene.add(p2)

      const starGeo = new THREE.BufferGeometry()
      const pos     = new Float32Array(600 * 3)
      for (let i = 0; i < pos.length; i++) pos[i] = (Math.random() - 0.5) * 60
      starGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
      const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.08, transparent: true, opacity: 0.6 }))
      scene.add(stars)

      const resize = () => {
        if (!canvasRef.current) return
        const w = canvasRef.current.clientWidth
        const h = canvasRef.current.clientHeight || 1
        renderer.setSize(w, h, false)
        camera.aspect = w / h
        camera.updateProjectionMatrix()
      }
      resize()
      window.addEventListener('resize', resize)

      let t = 0
      const animate = () => {
        if (disposed) return
        animId = requestAnimationFrame(animate)
        t += 0.01
        mesh.rotation.x = wireMesh.rotation.x = t * 0.3
        mesh.rotation.y = wireMesh.rotation.y = t * 0.5
        mesh.position.y = wireMesh.position.y = Math.sin(t * 0.8) * 0.15
        stars.rotation.y = t * 0.02
        renderer.render(scene, camera)
      }
      animate()

      return () => {
        disposed = true
        window.removeEventListener('resize', resize)
        cancelAnimationFrame(animId)

        // Force-release the WebGL context so the browser slot is freed
        const ext = renderer.getContext().getExtension('WEBGL_lose_context')
        ext?.loseContext()

        renderer.dispose()
        geo.dispose()
        mat.dispose()
        wireGeo.dispose()
        wireMat.dispose()
        starGeo.dispose()
      }
    }

    let cleanupFn: (() => void) | undefined
    loadThree().then(fn => { cleanupFn = fn })

    return () => {
      disposed = true
      cancelAnimationFrame(animId)
      cleanupFn?.()
    }
  }, [])

  return <canvas ref={canvasRef} className="w-full h-full" />
}
