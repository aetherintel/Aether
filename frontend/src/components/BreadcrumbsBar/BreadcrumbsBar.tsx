import { Anchor, Breadcrumbs, useComputedColorScheme } from '@mantine/core';
import { Link, useLocation } from 'react-router-dom';

export default function BreadcrumbsBar() {
  const computedColorScheme = useComputedColorScheme('light', {
    getInitialValueInEffect: true,
  });
  
  const location = useLocation();

  const pathnames = location.pathname.split('/').filter((x) => x);

  const crumbs = pathnames.map((segment, index) => {
    const to = `/${  pathnames.slice(0, index + 1).join('/')}`;
    const title = segment.charAt(0).toUpperCase() + segment.slice(1); // optional: format title

    return (
      <Anchor key={to} component={Link} to={to} c={computedColorScheme === 'dark' ? 'white' : 'black'}>
        {title}
      </Anchor>
    );
  });

  return (
    <Breadcrumbs separator=">" separatorMargin="md" mt="xs" mb="lg">
      <Anchor component={Link} to="/" c={computedColorScheme === 'dark' ? 'white' : 'black'}>Home</Anchor>
      {crumbs}
    </Breadcrumbs>
  );
}