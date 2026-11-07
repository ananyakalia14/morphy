"""Exercise account RPCs as authenticated users against disposable PostgreSQL."""

import asyncio
import os
import uuid

import asyncpg
import pytest


@pytest.mark.skipif(
    not os.getenv("MORPHY_INTEGRATION_DSN"), reason="Disposable PostgreSQL required"
)
def test_account_lifecycle():
    async def check():
        dsn = os.environ["MORPHY_INTEGRATION_DSN"]
        owner, guest, stranger = [uuid.uuid4() for _ in range(3)]
        admin = await asyncpg.connect(dsn)
        org = None

        async def rpc(user, sql, *args):
            conn = await asyncpg.connect(dsn)
            try:
                async with conn.transaction():
                    await conn.execute("SET LOCAL ROLE authenticated")
                    await conn.execute(
                        "SELECT set_config('request.jwt.claim.sub',$1,true)", str(user)
                    )
                    return await conn.fetchval(sql, *args)
            finally:
                await conn.close()

        try:
            for user in (owner, guest, stranger):
                await admin.execute("INSERT INTO auth.users(id) VALUES($1)", user)
                await rpc(
                    user,
                    "SELECT public.claim_profile($1,$2)",
                    "u_" + user.hex[:12],
                    "Original",
                )
            org = await rpc(owner, "SELECT public.create_workspace('Lifecycle test')")
            role = await admin.fetchval(
                "SELECT id FROM public.roles WHERE org_id=$1 AND name='VIEWER'", org
            )
            await rpc(
                owner,
                "SELECT public.update_profile($1,$2)",
                " Edited ",
                str(owner) + "/profile.webp",
            )
            profile = await admin.fetchrow(
                "SELECT username,display_name,avatar_path FROM public.profiles WHERE id=$1",
                owner,
            )
            assert profile["display_name"] == "Edited"
            assert profile["username"] == "u_" + owner.hex[:12]
            assert profile["avatar_path"] == str(owner) + "/profile.webp"
            with pytest.raises(asyncpg.CheckViolationError):
                await rpc(
                    guest,
                    "SELECT public.update_profile($1,$2)",
                    "Intruder",
                    str(owner) + "/profile.webp",
                )
            with pytest.raises(asyncpg.CheckViolationError):
                await rpc(owner, "SELECT public.update_profile($1,$2)", " ", None)
            await rpc(owner, "SELECT public.update_profile($1,$2)", "Edited", None)
            assert (
                await admin.fetchval(
                    "SELECT avatar_path FROM public.profiles WHERE id=$1", owner
                )
                is None
            )
            assert (
                await admin.fetchval(
                    "SELECT display_name FROM public.profiles WHERE id=$1", guest
                )
                == "Original"
            )

            await rpc(owner, "SELECT public.invite_person($1,$2,$3)", org, guest, role)
            inv = await admin.fetchval(
                "SELECT id FROM public.invitations WHERE org_id=$1", org
            )
            for user in (guest, stranger):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await rpc(user, "SELECT public.revoke_invitation($1)", inv)
            await rpc(owner, "SELECT public.revoke_invitation($1)", inv)
            await rpc(owner, "SELECT public.revoke_invitation($1)", inv)
            assert (
                await admin.fetchval(
                    "SELECT count(*) FROM public.audit_events WHERE org_id=$1 AND action='invitation.revoked'",
                    org,
                )
                == 1
            )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await rpc(guest, "SELECT public.accept_invitation($1)", inv)
            assert not await admin.fetchval(
                "SELECT EXISTS(SELECT FROM public.memberships WHERE org_id=$1 AND user_id=$2)",
                org,
                guest,
            )
            await rpc(owner, "SELECT public.invite_person($1,$2,$3)", org, guest, role)
            renewed = await admin.fetchval(
                "SELECT id FROM public.invitations WHERE org_id=$1", org
            )
            assert renewed != inv
            with pytest.raises(asyncpg.NoDataFoundError):
                await rpc(guest, "SELECT public.accept_invitation($1)", inv)
            with pytest.raises(asyncpg.NoDataFoundError):
                await rpc(stranger, "SELECT public.accept_invitation($1)", renewed)

            # Either acceptance or withdrawal wins; a revoked invite cannot create membership.
            outcomes = await asyncio.gather(
                rpc(owner, "SELECT public.revoke_invitation($1)", renewed),
                rpc(guest, "SELECT public.accept_invitation($1)", renewed),
                return_exceptions=True,
            )
            status = await admin.fetchval(
                "SELECT status FROM public.invitations WHERE id=$1", renewed
            )
            member = await admin.fetchval(
                "SELECT EXISTS(SELECT FROM public.memberships WHERE org_id=$1 AND user_id=$2)",
                org,
                guest,
            )
            assert (status, member) in [("accepted", True), ("revoked", False)]
            assert sum(isinstance(v, asyncpg.PostgresError) for v in outcomes) == 1
            if status == "revoked":
                await rpc(
                    owner, "SELECT public.invite_person($1,$2,$3)", org, guest, role
                )
                renewed = await admin.fetchval(
                    "SELECT id FROM public.invitations WHERE org_id=$1", org
                )
                await rpc(guest, "SELECT public.accept_invitation($1)", renewed)
            await rpc(guest, "SELECT public.accept_invitation($1)", renewed)
            with pytest.raises(asyncpg.RaiseError):
                await rpc(owner, "SELECT public.revoke_invitation($1)", renewed)
        finally:
            if org:
                await admin.execute("DELETE FROM public.organizations WHERE id=$1", org)
            await admin.execute(
                "DELETE FROM auth.users WHERE id=ANY($1::uuid[])",
                [owner, guest, stranger],
            )
            await admin.close()

    asyncio.run(check())
