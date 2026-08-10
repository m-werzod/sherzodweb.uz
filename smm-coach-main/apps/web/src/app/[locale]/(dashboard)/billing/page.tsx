import { getTranslations } from 'next-intl/server';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

// MVP davri: TO'LOV YO'Q — har bir funksiya bepul va ochiq (free-for-all invariant,
// billing gate hech narsani to'smaydi). Pulli rejalar Faza 2 rejasi, shuning uchun bu
// yerda faqat "kelajakda" sifatida ko'rsatiladi — faol "Subscribe" / narx reklamasi
// chalg'itmasligi uchun (hozir checkout darvozasi ataylab yo'q).
const FUTURE_PLANS = [
  {
    id: 'pro',
    name: 'billing.proPlan',
    features: ['Bir nechta brend/akkaunt', 'Jamoaviy kirish', 'Kengaytirilgan limitlar'],
  },
  {
    id: 'premium',
    name: 'billing.premiumPlan',
    features: ['Pro + avatar/ovoz generatsiyasi', 'Ustuvor qo\'llab-quvvatlash'],
  },
] as const;

const MVP_FEATURES = [
  "Cheksiz yo'l xaritasi va kontent vazifalari",
  'AI ssenariy + montaj + subtitr',
  "Ovozli AI murabbiy (platformani to'liq boshqaradi)",
  'Bilim vault + barcha agentlar',
];

export default async function BillingPage() {
  const t = await getTranslations();

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{t('billing.title')}</h1>
        <p className="text-sm text-(--color-muted-foreground)">
          MVP davrida hamma narsa <strong>bepul</strong> — to'lov yo'q, hech bir funksiya yopilmagan.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            {t('billing.freePlan')}
            <Badge>Joriy</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-3xl font-bold">Bepul</div>
          <ul className="space-y-1 text-sm text-(--color-muted-foreground)">
            {MVP_FEATURES.map((f) => (
              <li key={f}>• {f}</li>
            ))}
          </ul>
          <Button className="w-full" disabled>
            Faollashtirilgan
          </Button>
        </CardContent>
      </Card>

      <div className="space-y-2">
        <h2 className="text-sm font-medium text-(--color-muted-foreground)">
          Kelajakdagi rejalar (hozircha kerak emas)
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          {FUTURE_PLANS.map((plan) => (
            <Card key={plan.id} className="opacity-60">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  {t(plan.name)}
                  <Badge variant="secondary">Tez orada</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="text-sm text-(--color-muted-foreground)">
                  Monetizatsiya Faza 2 — MVP yakunlangach.
                </div>
                <ul className="space-y-1 text-sm text-(--color-muted-foreground)">
                  {plan.features.map((f) => (
                    <li key={f}>• {f}</li>
                  ))}
                </ul>
                <Button className="w-full" disabled>
                  Tez orada
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
