import Link from 'next/link'

const socials = [
  {
    href: 'https://github.com/m-werzod',
    src: 'https://img.icons8.com/3d-fluency/94/github.png',
    alt: 'GitHub',
  },
  {
    href: 'https://t.me/WerzodUsmanov',
    src: 'https://cdn-icons-png.flaticon.com/512/2111/2111646.png',
    alt: 'Telegram',
  },
  {
    href: 'https://instagram.com/Sherzod_usmanovv',
    src: 'https://cdn-icons-png.flaticon.com/512/15713/15713420.png',
    alt: 'Instagram',
  },
  {
    href: 'https://www.linkedin.com/in/sherzod-usmonjonov-8b22713b0/',
    src: 'https://cdn-icons-png.flaticon.com/512/3992/3992606.png',
    alt: 'LinkedIn',
  },
]

export default function Footer() {
  return (
    <footer className="border-t border-white/5 bg-[#020617] py-12 px-6">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <p className="text-xl font-bold">
            <span className="text-white">Sherzod</span>
            <span className="text-[#38bdf8]">dev</span>
          </p>
          <p className="text-sm text-slate-500 mt-1">Full-Stack Engineer & AI Integration Specialist</p>
        </div>

        <div className="flex items-center gap-4">
          {socials.map((s) => (
            <Link
              key={s.alt}
              href={s.href}
              target="_blank"
              rel="noopener noreferrer"
              className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/5 hover:bg-white/10 transition-colors duration-200 group"
            >
              <img
                src={s.src}
                alt={s.alt}
                width={20}
                height={20}
                className="w-5 h-5 object-contain group-hover:scale-110 transition-transform"
              />
            </Link>
          ))}
        </div>

        <p className="text-xs text-slate-600">
          © {new Date().getFullYear()} Sherzodbek Usmonjonov. All rights reserved.
        </p>
      </div>
    </footer>
  )
}
