import { Breadcrumbs, Anchor } from '@mantine/core';

const items = [
  { title: 'HTIT-Monitor', href: '#' },
  { title: 'Cases', href: '#' },
].map((item, index) => (
  <Anchor href={item.href} key={index} c="black">
    {item.title}
  </Anchor>
));

export default function BreadcrumbsBar() {
  return (
    <>
      <Breadcrumbs separator=">" separatorMargin="md" mt="xs" mb="lg">
        {items}
      </Breadcrumbs>
    </>
  );
}