import { useEffect, useMemo, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  useInviteMember,
  useRemoveMember,
  useTenantMembers,
  useUpdateMemberRole,
} from "@/hooks/useTenants";
import { useAuthStore } from "@/store/auth";
import type { TenantMember, TenantRole } from "@/types";

const OWNER_ROLES: TenantRole[] = ["owner", "admin", "member", "viewer"];
const ADMIN_ROLES: TenantRole[] = ["admin", "member", "viewer"];

function roleLabel(role: TenantRole): string {
  return role.charAt(0).toUpperCase() + role.slice(1);
}

export function TeamPage() {
  const { data: members, isLoading, error } = useTenantMembers();
  const inviteMember = useInviteMember();
  const updateMemberRole = useUpdateMemberRole();
  const removeMember = useRemoveMember();
  const { user, memberships, currentTenantId } = useAuthStore();

  const currentMembership = memberships.find((m) => m.tenant_id === currentTenantId);
  const canManage = currentMembership?.role === "owner" || currentMembership?.role === "admin";
  const canAssignOwner = currentMembership?.role === "owner";

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<TenantRole>("member");
  const [statusMessage, setStatusMessage] = useState("");
  const [roleDrafts, setRoleDrafts] = useState<Record<string, TenantRole>>({});

  useEffect(() => {
    if (!members) return;
    const nextDrafts: Record<string, TenantRole> = {};
    for (const member of members) {
      nextDrafts[member.user_id] = member.role;
    }
    setRoleDrafts(nextDrafts);
  }, [members]);

  const sortedMembers = useMemo(() => {
    if (!members) return [];
    return [...members].sort((a, b) => a.email.localeCompare(b.email));
  }, [members]);

  const inviteRoles = canAssignOwner ? OWNER_ROLES : ADMIN_ROLES;

  const roleOptionsForMember = (member: TenantMember): TenantRole[] => {
    if (canAssignOwner) return OWNER_ROLES;
    if (member.role === "owner") return OWNER_ROLES;
    return ADMIN_ROLES;
  };

  const canEditMember = (member: TenantMember): boolean => {
    if (!canManage || !user) return false;
    if (member.user_id === user.id) return false;
    if (!canAssignOwner && member.role === "owner") return false;
    return true;
  };

  const handleInvite = async () => {
    if (!inviteEmail.trim() || !canManage) return;
    setStatusMessage("");
    try {
      await inviteMember.mutateAsync({
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      setInviteEmail("");
      setInviteRole("member");
      setStatusMessage("Invitation successful. The user was added to this tenant.");
    } catch (err: any) {
      setStatusMessage(err?.response?.data?.detail || "Failed to invite member.");
    }
  };

  const handleUpdateRole = async (member: TenantMember) => {
    const nextRole = roleDrafts[member.user_id] || member.role;
    if (nextRole === member.role) return;
    setStatusMessage("");
    try {
      await updateMemberRole.mutateAsync({
        userId: member.user_id,
        role: nextRole,
      });
      setStatusMessage(`Updated role for ${member.email}.`);
    } catch (err: any) {
      setRoleDrafts((prev) => ({ ...prev, [member.user_id]: member.role }));
      setStatusMessage(err?.response?.data?.detail || "Failed to update role.");
    }
  };

  const handleRemove = async (member: TenantMember) => {
    if (!canEditMember(member)) return;
    if (!confirm(`Remove ${member.email} from this tenant?`)) return;
    setStatusMessage("");
    try {
      await removeMember.mutateAsync(member.user_id);
      setStatusMessage(`Removed ${member.email} from this tenant.`);
    } catch (err: any) {
      setStatusMessage(err?.response?.data?.detail || "Failed to remove member.");
    }
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Team</h1>
        <p className="mt-1 text-muted-foreground">
          Manage users and roles for the current tenant.
        </p>
      </div>

      {canManage && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Invite Member</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_160px_auto]">
              <Input
                placeholder="user@example.com"
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
              />
              <select
                className="h-10 rounded-md border border-border bg-background px-3 text-sm"
                value={inviteRole}
                onChange={(event) => setInviteRole(event.target.value as TenantRole)}
              >
                {inviteRoles.map((role) => (
                  <option key={role} value={role}>
                    {roleLabel(role)}
                  </option>
                ))}
              </select>
              <Button onClick={handleInvite} disabled={inviteMember.isPending || !inviteEmail.trim()}>
                {inviteMember.isPending ? "Inviting..." : "Invite"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Members</CardTitle>
        </CardHeader>
        <CardContent>
          {statusMessage && (
            <p className="mb-4 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
              {statusMessage}
            </p>
          )}

          {!canManage && (
            <p className="mb-4 text-sm text-muted-foreground">
              You can view members, but only owners/admins can make changes.
            </p>
          )}

          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading members...</p>
          ) : error ? (
            <p className="text-sm text-destructive">Failed to load members.</p>
          ) : (
            <div className="space-y-3">
              {sortedMembers.map((member) => {
                const editable = canEditMember(member);
                const roleDraft = roleDrafts[member.user_id] || member.role;
                const canSubmitRoleChange = editable && roleDraft !== member.role;
                const updatePendingForMember =
                  updateMemberRole.isPending && updateMemberRole.variables?.userId === member.user_id;
                const removePendingForMember =
                  removeMember.isPending && removeMember.variables === member.user_id;

                return (
                  <div
                    key={member.user_id}
                    className="flex flex-col gap-3 rounded-md border border-border p-3 md:flex-row md:items-center md:justify-between"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium">{member.full_name}</p>
                      <p className="truncate text-sm text-muted-foreground">{member.email}</p>
                    </div>

                    <div className="flex items-center gap-2">
                      <select
                        className="h-9 min-w-[120px] rounded-md border border-border bg-background px-2 text-sm"
                        value={roleDraft}
                        disabled={!editable || updatePendingForMember}
                        onChange={(event) =>
                          setRoleDrafts((prev) => ({
                            ...prev,
                            [member.user_id]: event.target.value as TenantRole,
                          }))
                        }
                      >
                        {roleOptionsForMember(member).map((role) => (
                          <option key={role} value={role}>
                            {roleLabel(role)}
                          </option>
                        ))}
                      </select>

                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!canSubmitRoleChange || updatePendingForMember}
                        onClick={() => handleUpdateRole(member)}
                      >
                        {updatePendingForMember ? "Saving..." : "Update"}
                      </Button>

                      <Button
                        variant="destructive"
                        size="sm"
                        disabled={!editable || removePendingForMember}
                        onClick={() => handleRemove(member)}
                      >
                        {removePendingForMember ? "Removing..." : "Remove"}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
