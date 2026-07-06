import HeroSection from '@/components/hero/HeroSection'
import TrustStrip from '@/components/sections/TrustStrip'
import CategorySelector from '@/components/sections/CategorySelector'
import TechStack from '@/components/sections/TechStack'
import ProjectsPreview from '@/components/sections/ProjectsPreview'

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <TrustStrip />
      <CategorySelector />
      <TechStack />
      <ProjectsPreview />
    </>
  )
}
