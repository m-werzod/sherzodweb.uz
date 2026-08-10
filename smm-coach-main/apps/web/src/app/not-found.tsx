import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-6">
      <h1 className="text-3xl font-semibold">404</h1>
      <p className="text-(--color-muted-foreground)">Sahifa topilmadi</p>
      <Button asChild>
        <Link href="/">Bosh sahifaga qaytish</Link>
      </Button>
    </div>
  );
}
