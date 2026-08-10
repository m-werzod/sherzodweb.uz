import { getTranslations } from 'next-intl/server';

export default async function TasksPage() {
  const t = await getTranslations();
  return (
    <div>
      <h1 className="text-2xl font-semibold">{t('nav.tasks')}</h1>
      <p className="text-sm text-(--color-muted-foreground) mt-2">
        Tez orada vazifalar bo'yicha kanban ko'rinishi qo'shiladi.
      </p>
    </div>
  );
}
