import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function SectionCards() {
  let token = localStorage.getItem('token')
  if (token) {
    token = token.substring(0, 100) + '...';
  }

  return (
    <div className="*:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card dark:*:data-[slot=card]:bg-card grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-1">
      <Card className="@container/card">
        <CardHeader>
          <CardDescription>User Token</CardDescription>
          <CardTitle className="text-1xl font-semibold tabular-nums @[250px]/card:text-1xl">
            {token}
          </CardTitle>
        </CardHeader>
      </Card>
    </div>
  )
}
