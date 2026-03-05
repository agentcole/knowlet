import { useAuthStore } from "@/store/auth";
import { useDocuments } from "@/hooks/useDocuments";
import { useWikiTree } from "@/hooks/useWiki";
import { useChatSessions } from "@/hooks/useChat";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, BookOpen, MessageSquare, Mic } from "lucide-react";
import { Link } from "react-router-dom";

export function DashboardPage() {
  const { user, memberships, currentTenantId } = useAuthStore();
  const tenant = memberships.find((m) => m.tenant_id === currentTenantId);
  const { data: documents } = useDocuments();
  const { data: wikiTree } = useWikiTree();
  const { data: chatSessions } = useChatSessions();

  const totalPages = wikiTree
    ? wikiTree.categories.reduce((sum, c) => sum + c.pages.length, 0) + wikiTree.uncategorized_pages.length
    : 0;

  const stats = [
    { label: "Documents", value: documents?.total ?? 0, icon: FileText, path: "/documents" },
    { label: "Wiki Pages", value: totalPages, icon: BookOpen, path: "/wiki" },
    { label: "Chat Sessions", value: chatSessions?.length ?? 0, icon: MessageSquare, path: "/chat" },
  ];

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Welcome back, {user?.full_name}</h1>
        <p className="text-muted-foreground mt-1">{tenant?.tenant_name}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Link key={stat.label} to={stat.path}>
              <Card className="hover:shadow-md transition-shadow">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {stat.label}
                  </CardTitle>
                  <Icon size={20} className="text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{stat.value}</p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
