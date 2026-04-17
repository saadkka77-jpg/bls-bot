import asyncio
import datetime as dt
import io
import json
import os
from threading import Thread
from typing import Any

import discord
from discord.ext import commands, tasks
from flask import Flask

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


RIYADH_TZ = dt.timezone(dt.timedelta(hours=3))
DATA_FILE = "bot_data.json"

TOKEN = os.getenv("TOKEN")

LOG_TICKET_ID = 1480456866613170267
VACATION_ROLE_ID = 1492607429249339502
WARNING_ROLE_ID = 1493332501811171470
WARNING_CHANNEL_ID = 1480389401535189065
LEAVE_PANEL_CHANNEL_ID = 1490070238270718013
LEAVE_LOG_CHANNEL_ID = 1490820000477610036
TICKET_SETUP_CHANNEL_ID = 1481127399042322582

SUPPORT_ROLES = [
    1477492633847857252,
    1482194383515422752,
    1480443913557905499,
]

STORE_ROLES = [
    1478970736717598840,
    1490386915629989948,
    1478971845729583276,
]

TICKET_TYPES = {
    "support": {
        "label": "دعم فني",
        "category_id": 1487721982945394728,
        "staff_roles": SUPPORT_ROLES,
        "prompt": "حياك الله، اكتب استفسارك.",
        "emoji": "🛠️",
    },
    "store": {
        "label": "تكت متجر",
        "category_id": 1487848330804330699,
        "staff_roles": STORE_ROLES,
        "prompt": "حياك الله، اكتب المنتج الي تبغاه.",
        "emoji": "🛒",
    },
    "rank": {
        "label": "الرانك",
        "category_id": 1494665237717323907,
        "staff_roles": STORE_ROLES,
        "prompt": "حياك الله، اكتب الرانك المطلوب وكل التفاصيل المهمة.",
        "emoji": "🏅",
    },
    "admin_report": {
        "label": "شكوه على اداري",
        "category_id": 1487709726765748295,
        "staff_roles": STORE_ROLES,
        "prompt": (
            "حياك الله، اكتب ملخص الشكوة مع الدليل، "
            "وإذا مرت 24 ساعة على الي صار تعتبر الشكوة مرفوضة."
        ),
        "emoji": "⚠️",
    },
    "player_report": {
        "label": "شكوه على شخص",
        "category_id": 1494665311331291258,
        "staff_roles": SUPPORT_ROLES,
        "prompt": (
            "حياك الله، اكتب ملخص الشكوة مع الدليل، "
            "وإذا مرت 24 ساعة على الي صار تعتبر الشكوة مرفوضة."
        ),
        "emoji": "📌",
    },
}


def now_riyadh() -> dt.datetime:
    return dt.datetime.now(RIYADH_TZ)


def iso_now() -> str:
    return now_riyadh().isoformat()


def parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=RIYADH_TZ)
    return parsed.astimezone(RIYADH_TZ)


def month_key() -> str:
    return now_riyadh().strftime("%Y-%m")


def default_data() -> dict[str, Any]:
    return {
        "ticket_count": 0,
        "tickets": {},
        "leaves": {
            "balances": {},
            "active": {},
            "withdrawals": {},
            "month_key": month_key(),
        },
        "warnings": {},
    }


def load_data() -> dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return default_data()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return default_data()

    base = default_data()
    base.update(data)
    base["tickets"] = data.get("tickets", {})
    base["warnings"] = data.get("warnings", {})
    base["leaves"] = {
        "balances": data.get("leaves", {}).get("balances", {}),
        "active": data.get("leaves", {}).get("active", {}),
        "withdrawals": data.get("leaves", {}).get("withdrawals", {}),
        "month_key": data.get("leaves", {}).get("month_key", month_key()),
    }
    return base


DATA = load_data()


def save_data() -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(DATA, file, indent=4, ensure_ascii=False)


def reset_monthly_leave_balances_if_needed() -> None:
    current_month = month_key()
    leave_data = DATA["leaves"]
    if leave_data.get("month_key") == current_month:
        return

    leave_data["month_key"] = current_month
    active_ids = set(leave_data["active"].keys())
    member_ids = set(leave_data["balances"].keys()) | active_ids
    leave_data["withdrawals"] = {}

    for user_id in member_ids:
        active_leave = leave_data["active"].get(user_id)
        used_days = active_leave["days"] if active_leave else 0
        leave_data["balances"][user_id] = max(14 - used_days, 0)

    save_data()


def get_leave_balance(user_id: int) -> int:
    reset_monthly_leave_balances_if_needed()
    uid = str(user_id)
    balances = DATA["leaves"]["balances"]
    if uid not in balances:
        balances[uid] = 14
        save_data()
    return balances[uid]


def user_has_active_warning(user_id: int) -> bool:
    active = DATA["warnings"].get(str(user_id), [])
    now = now_riyadh()
    return any(parse_dt(item.get("ends_at")) and parse_dt(item.get("ends_at")) > now for item in active)


async def safe_delete_message(message: discord.Message | None) -> None:
    if not message:
        return
    try:
        await message.delete()
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass


async def send_temp_message(channel: discord.abc.Messageable, content: str) -> None:
    try:
        msg = await channel.send(content)
        await asyncio.sleep(8)
        await safe_delete_message(msg)
    except (discord.Forbidden, discord.HTTPException):
        pass


def member_has_ticket_staff_role(member: discord.Member, role_ids: list[int]) -> bool:
    return any(role.id in role_ids for role in member.roles)


def make_ticket_name(ticket_number: int, ticket_type: str) -> str:
    label = TICKET_TYPES[ticket_type]["label"].replace(" ", "-")
    return f"{label}-{ticket_number}"


async def sync_claim_permissions(channel: discord.TextChannel, opener: discord.Member, claimer: discord.Member, role_ids: list[int]) -> None:
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        channel.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        channel.guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            attach_files=True,
            embed_links=True,
        ),
        opener: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        ),
        claimer: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            manage_messages=True,
        ),
    }

    for role_id in role_ids:
        role = channel.guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                read_message_history=True,
            )

    await channel.edit(overwrites=overwrites)


async def apply_warning_role(member: discord.Member) -> None:
    role = member.guild.get_role(WARNING_ROLE_ID)
    if role and role not in member.roles:
        await member.add_roles(role, reason="Active administrative warning")


async def remove_warning_role_if_clear(member: discord.Member) -> None:
    role = member.guild.get_role(WARNING_ROLE_ID)
    if role and role in member.roles and not user_has_active_warning(member.id):
        await member.remove_roles(role, reason="All administrative warnings expired or removed")


async def log_warning_action(title: str, description: str, member: discord.Member, color: int) -> None:
    channel = bot.get_channel(WARNING_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(title=title, description=description, color=color, timestamp=now_riyadh())
    embed.add_field(name="العضو", value=member.mention, inline=False)
    await channel.send(content=member.mention, embed=embed)


async def add_warning(member: discord.Member, duration_days: int, reason: str, issued_by: discord.abc.User, source: str) -> None:
    uid = str(member.id)
    starts_at = now_riyadh()
    ends_at = starts_at + dt.timedelta(days=duration_days)
    warning_entry = {
        "reason": reason,
        "duration_days": duration_days,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "issued_by": issued_by.id,
        "source": source,
    }

    DATA["warnings"].setdefault(uid, []).append(warning_entry)
    save_data()

    await apply_warning_role(member)
    await log_warning_action(
        title="نزول إنذار إداري",
        description=(
            f"تم تسجيل إنذار إداري على {member.mention}\n"
            f"السبب: {reason}\n"
            f"المدة: {duration_days} يوم\n"
            f"بواسطة: {issued_by.mention}"
        ),
        member=member,
        color=0xE74C3C,
    )


async def clear_all_warnings(member: discord.Member, removed_by: discord.abc.User, reason: str, source: str) -> int:
    uid = str(member.id)
    warnings = DATA["warnings"].get(uid, [])
    if not warnings:
        return 0

    removed_count = len(warnings)
    DATA["warnings"][uid] = []
    save_data()
    await remove_warning_role_if_clear(member)

    await log_warning_action(
        title="سحب إنذار إداري",
        description=(
            f"تم سحب الإنذار عن {member.mention}\n"
            f"السبب: {reason}\n"
            f"سحب بواسطة: {removed_by.mention}\n"
            f"نوع السحب: {source}"
        ),
        member=member,
        color=0x2ECC71,
    )
    return removed_count


async def expire_warning_entry(guild: discord.Guild, user_id: str, warning: dict[str, Any]) -> None:
    member = guild.get_member(int(user_id))
    if not member:
        return

    await remove_warning_role_if_clear(member)
    await log_warning_action(
        title="انتهاء إنذار إداري",
        description=(
            f"انتهت مدة الإنذار عن {member.mention}\n"
            f"السبب: {warning.get('reason', 'غير محدد')}\n"
            f"المدة: {warning.get('duration_days', 0)} يوم"
        ),
        member=member,
        color=0x3498DB,
    )


async def close_ticket_with_reason(interaction: discord.Interaction, reason: str) -> None:
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return

    ticket_data = DATA["tickets"].get(str(channel.id))
    if not ticket_data:
        await interaction.followup.send("هذه التذكرة غير مسجلة في النظام.", ephemeral=True)
        return

    opener = interaction.guild.get_member(ticket_data["opener_id"])
    closed_at = now_riyadh()

    log_lines = [
        f"اسم التذكرة: {channel.name}",
        f"القسم: {ticket_data.get('type_label', 'غير معروف')}",
        f"صاحب التذكرة: {ticket_data.get('opener_name', 'غير معروف')}",
        f"أغلقها: {interaction.user} ({interaction.user.id})",
        f"سبب الإغلاق: {reason}",
        f"وقت الإغلاق: {closed_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "-" * 60,
    ]

    async for message in channel.history(limit=None, oldest_first=True):
        created = message.created_at.astimezone(RIYADH_TZ).strftime("%Y-%m-%d %H:%M")
        attachments = ", ".join(attachment.url for attachment in message.attachments)
        content = message.content or "[بدون نص]"
        if attachments:
            content = f"{content} | Attachments: {attachments}"
        log_lines.append(f"[{created}] {message.author} ({message.author.id}): {content}")

    transcript = "\n".join(log_lines)
    log_channel = interaction.client.get_channel(LOG_TICKET_ID)
    if log_channel:
        transcript_file = discord.File(
            fp=io.BytesIO(transcript.encode("utf-8")),
            filename=f"{channel.name}.txt",
        )
        embed = discord.Embed(
            title="إغلاق تذكرة",
            color=0xC0392B,
            timestamp=closed_at,
        )
        embed.add_field(name="التذكرة", value=channel.name, inline=False)
        embed.add_field(name="القسم", value=ticket_data.get("type_label", "غير معروف"), inline=True)
        embed.add_field(name="أغلقها", value=interaction.user.mention, inline=True)
        embed.add_field(name="السبب", value=reason, inline=False)
        await log_channel.send(embed=embed, file=transcript_file)

    if opener:
        dm_embed = discord.Embed(
            title="تم إغلاق تذكرتك",
            description=(
                f"تم إغلاق تذكرتك بواسطة {interaction.user.mention}\n"
                f"السبب: {reason}\n"
                f"التاريخ والوقت: {closed_at.strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            color=0x2F3136,
            timestamp=closed_at,
        )
        dm_embed.set_footer(text="BLS Ticket System")
        try:
            await opener.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    DATA["tickets"].pop(str(channel.id), None)
    save_data()
    await channel.delete(reason=f"Ticket closed by {interaction.user}")


class TicketCloseModal(discord.ui.Modal, title="إغلاق التذكرة"):
    reason = discord.ui.TextInput(
        label="سبب الإغلاق",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return

        ticket_data = DATA["tickets"].get(str(channel.id))
        if not ticket_data:
            await interaction.followup.send("هذه التذكرة غير موجودة في قاعدة البيانات.", ephemeral=True)
            return

        staff_roles = ticket_data.get("staff_roles", [])
        claimer_id = ticket_data.get("claimer_id")
        is_staff = isinstance(interaction.user, discord.Member) and member_has_ticket_staff_role(interaction.user, staff_roles)

        if not is_staff:
            await interaction.followup.send("لا تملك صلاحية إغلاق هذه التذكرة.", ephemeral=True)
            return

        if claimer_id and interaction.user.id != claimer_id:
            await interaction.followup.send("فقط الشخص الذي استلم التذكرة يقدر يقفلها.", ephemeral=True)
            return

        await close_ticket_with_reason(interaction, self.reason.value)


class TicketActionView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="استلام",
        style=discord.ButtonStyle.success,
        custom_id="ticket_claim",
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("تعذر تنفيذ العملية هنا.", ephemeral=True)
            return

        ticket_data = DATA["tickets"].get(str(channel.id))
        if not ticket_data:
            await interaction.response.send_message("هذه التذكرة غير مسجلة.", ephemeral=True)
            return

        staff_roles = ticket_data["staff_roles"]
        if not member_has_ticket_staff_role(interaction.user, staff_roles):
            await interaction.response.send_message("هذا الزر مخصص للرتب المخولة فقط.", ephemeral=True)
            return

        if ticket_data.get("claimer_id"):
            claimer = interaction.guild.get_member(ticket_data["claimer_id"])
            name = claimer.mention if claimer else "شخص آخر"
            await interaction.response.send_message(f"هذه التذكرة مستلمة مسبقًا من {name}.", ephemeral=True)
            return

        opener = interaction.guild.get_member(ticket_data["opener_id"])
        if not opener:
            await interaction.response.send_message("لم يتم العثور على صاحب التذكرة.", ephemeral=True)
            return

        ticket_data["claimer_id"] = interaction.user.id
        ticket_data["claimer_name"] = str(interaction.user)
        ticket_data["claimed_at"] = iso_now()
        DATA["tickets"][str(channel.id)] = ticket_data
        save_data()

        await sync_claim_permissions(channel, opener, interaction.user, staff_roles)

        button.disabled = True
        button.label = f"تم الاستلام بواسطة {interaction.user.display_name}"

        embed = discord.Embed(
            title="تم استلام التذكرة",
            description=(
                f"تم استلام هذه التذكرة رسميًا من قبل {interaction.user.mention}.\n"
                f"من الآن الرسائل داخل التذكرة ستكون بين المستلم وصاحب التذكرة فقط."
            ),
            color=0x2ECC71,
            timestamp=now_riyadh(),
        )
        embed.set_footer(text="BLS Ticket System")

        await interaction.response.edit_message(view=self)
        await channel.send(content=f"{interaction.user.mention} {opener.mention}", embed=embed)

    @discord.ui.button(
        label="إغلاق",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close",
    )
    async def close_ticket(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("تعذر تنفيذ العملية هنا.", ephemeral=True)
            return

        ticket_data = DATA["tickets"].get(str(channel.id))
        if not ticket_data:
            await interaction.response.send_message("هذه التذكرة غير مسجلة.", ephemeral=True)
            return

        if not member_has_ticket_staff_role(interaction.user, ticket_data["staff_roles"]):
            await interaction.response.send_message("لا تملك صلاحية إغلاق هذه التذكرة.", ephemeral=True)
            return

        claimer_id = ticket_data.get("claimer_id")
        if claimer_id and interaction.user.id != claimer_id:
            await interaction.response.send_message("فقط الشخص الذي استلم التذكرة يقدر يقفلها.", ephemeral=True)
            return

        await interaction.response.send_modal(TicketCloseModal())


class TicketDropdown(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label=config["label"],
                value=key,
                emoji=config["emoji"],
            )
            for key, config in TICKET_TYPES.items()
        ]

        super().__init__(
            placeholder="اختر نوع التذكرة...",
            options=options,
            custom_id="ticket_select_menu",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("لا يمكن إنشاء تذكرة هنا.", ephemeral=True)
            return

        ticket_type = self.values[0]
        config = TICKET_TYPES[ticket_type]
        category = interaction.guild.get_channel(config["category_id"])
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("تعذر العثور على قسم التذاكر المحدد.", ephemeral=True)
            return

        for ticket_info in DATA["tickets"].values():
            if ticket_info.get("opener_id") == interaction.user.id and not ticket_info.get("closed_at"):
                existing_channel = interaction.guild.get_channel(int(ticket_info["channel_id"]))
                if existing_channel:
                    await interaction.response.send_message(
                        f"عندك تذكرة مفتوحة بالفعل: {existing_channel.mention}",
                        ephemeral=True,
                    )
                    return

        DATA["ticket_count"] += 1
        ticket_number = DATA["ticket_count"]

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                attach_files=True,
                embed_links=True,
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
        }

        for role_id in config["staff_roles"]:
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )

        channel = await interaction.guild.create_text_channel(
            name=make_ticket_name(ticket_number, ticket_type),
            category=category,
            overwrites=overwrites,
            topic=f"Ticket Owner: {interaction.user.id} | Type: {ticket_type}",
            reason=f"Ticket created by {interaction.user}",
        )

        DATA["tickets"][str(channel.id)] = {
            "channel_id": channel.id,
            "opener_id": interaction.user.id,
            "opener_name": str(interaction.user),
            "type": ticket_type,
            "type_label": config["label"],
            "staff_roles": config["staff_roles"],
            "claimer_id": None,
            "claimer_name": None,
            "created_at": iso_now(),
        }
        save_data()

        embed = discord.Embed(
            title=f"تذكرة {config['label']}",
            description=config["prompt"],
            color=0x2F3136,
            timestamp=now_riyadh(),
        )
        embed.set_footer(text="BLS Ticket System")

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketActionView(),
        )
        await interaction.response.send_message(
            f"تم فتح التذكرة بنجاح: {channel.mention}",
            ephemeral=True,
        )


class TicketPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


class LeaveView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="طلب إجازة",
        style=discord.ButtonStyle.success,
        emoji="📝",
        custom_id="vacation_request",
    )
    async def request_leave(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("لا يمكن تنفيذ هذا الطلب هنا.", ephemeral=True)
            return

        reset_monthly_leave_balances_if_needed()
        uid = str(interaction.user.id)

        if user_has_active_warning(interaction.user.id):
            await interaction.response.send_message("لا تقدر تطلب إجازة لأن عليك إنذارًا إداريًا فعالًا.", ephemeral=True)
            return

        if uid in DATA["leaves"]["active"]:
            await interaction.response.send_message("عندك إجازة مفعلة بالفعل.", ephemeral=True)
            return

        balance = get_leave_balance(interaction.user.id)
        if balance <= 0:
            await interaction.response.send_message("رصيد إجازاتك لهذا الشهر انتهى.", ephemeral=True)
            return

        role = interaction.guild.get_role(VACATION_ROLE_ID)
        if not role:
            await interaction.response.send_message("رتبة الإجازة غير موجودة.", ephemeral=True)
            return

        started_at = now_riyadh()
        ends_at = started_at + dt.timedelta(days=balance)
        DATA["leaves"]["active"][uid] = {
            "started_at": started_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "days": balance,
        }
        DATA["leaves"]["balances"][uid] = 0
        save_data()

        await interaction.user.add_roles(role, reason="Vacation requested")

        log_channel = interaction.client.get_channel(LEAVE_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="تفعيل إجازة",
                description=(
                    f"تم تفعيل الإجازة لـ {interaction.user.mention}\n"
                    f"المدة: {balance} يوم\n"
                    f"تبدأ: {started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"تنتهي: {ends_at.strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                color=0x2ECC71,
                timestamp=started_at,
            )
            await log_channel.send(content=interaction.user.mention, embed=embed)

        await interaction.response.send_message(
            f"تم تفعيل الإجازة لك بنجاح لمدة {balance} يوم.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="سحب إجازة",
        style=discord.ButtonStyle.danger,
        emoji="📤",
        custom_id="vacation_withdraw",
    )
    async def withdraw_leave(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("لا يمكن تنفيذ هذا الطلب هنا.", ephemeral=True)
            return

        uid = str(interaction.user.id)
        leave_entry = DATA["leaves"]["active"].get(uid)
        if not leave_entry:
            await interaction.response.send_message("ليس لديك إجازة مفعلة حاليًا.", ephemeral=True)
            return

        started_at = parse_dt(leave_entry.get("started_at"))
        if not started_at:
            await interaction.response.send_message("بيانات الإجازة غير صالحة.", ephemeral=True)
            return

        now = now_riyadh()
        duration_hours = (now - started_at).total_seconds() / 3600
        today_key = now.strftime("%Y-%m-%d")
        user_history = DATA["leaves"]["withdrawals"].setdefault(uid, [])
        same_day_withdrawals = [item for item in user_history if item.get("date") == today_key]

        warning_reason = None
        warning_days = None
        if len(same_day_withdrawals) >= 1:
            warning_reason = "سحب الإجازة مرتين في نفس اليوم"
            warning_days = 3
        elif duration_hours > 24:
            warning_reason = "سحب الإجازة بعد مرور 24 ساعة من بدء الإجازة"
            warning_days = 7

        DATA["leaves"]["active"].pop(uid, None)
        user_history.append({"date": today_key, "at": now.isoformat()})
        save_data()

        role = interaction.guild.get_role(VACATION_ROLE_ID)
        if role and role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason="Vacation withdrawn")

        log_channel = interaction.client.get_channel(LEAVE_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="سحب إجازة",
                description=(
                    f"تم سحب الإجازة من {interaction.user.mention}\n"
                    f"وقت السحب: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                color=0xE67E22,
                timestamp=now,
            )
            if warning_reason and warning_days:
                embed.add_field(
                    name="نتيجة السحب",
                    value=f"تم تنزيل إنذار إداري\nالسبب: {warning_reason}\nالمدة: {warning_days} يوم",
                    inline=False,
                )
            await log_channel.send(content=interaction.user.mention, embed=embed)

        if warning_reason and warning_days:
            await add_warning(
                member=interaction.user,
                duration_days=warning_days,
                reason=warning_reason,
                issued_by=bot.user,
                source="auto_leave_withdraw",
            )

        message = "تم سحب الإجازة بنجاح."
        if warning_reason and warning_days:
            message += f" وتم تنزيل إنذار إداري لمدة {warning_days} يوم بسبب: {warning_reason}."

        await interaction.response.send_message(message, ephemeral=True)


app = Flask("")


@app.route("/")
def home() -> str:
    return "BLS Ticket System is Online!"


def run_web() -> None:
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)


def keep_alive() -> None:
    thread = Thread(target=run_web)
    thread.daemon = True
    thread.start()


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


@tasks.loop(minutes=1)
async def housekeeping() -> None:
    reset_monthly_leave_balances_if_needed()
    now = now_riyadh()

    for guild in bot.guilds:
        warning_changed = False
        for user_id, warnings in list(DATA["warnings"].items()):
            expired = []
            active = []
            for warning in warnings:
                ends_at = parse_dt(warning.get("ends_at"))
                if ends_at and ends_at <= now:
                    expired.append(warning)
                else:
                    active.append(warning)

            if expired:
                DATA["warnings"][user_id] = active
                warning_changed = True
                for warning in expired:
                    await expire_warning_entry(guild, user_id, warning)

        if warning_changed:
            save_data()

        leave_changed = False
        for user_id, leave_info in list(DATA["leaves"]["active"].items()):
            ends_at = parse_dt(leave_info.get("ends_at"))
            if not ends_at or ends_at > now:
                continue

            member = guild.get_member(int(user_id))
            role = guild.get_role(VACATION_ROLE_ID)
            if member and role and role in member.roles:
                await member.remove_roles(role, reason="Vacation expired")

            DATA["leaves"]["active"].pop(user_id, None)
            leave_changed = True

            log_channel = bot.get_channel(LEAVE_LOG_CHANNEL_ID)
            if log_channel and member:
                embed = discord.Embed(
                    title="انتهاء إجازة",
                    description=f"انتهت إجازة {member.mention} تلقائيًا.",
                    color=0x3498DB,
                    timestamp=now,
                )
                await log_channel.send(content=member.mention, embed=embed)

        if leave_changed:
            save_data()


@housekeeping.before_loop
async def before_housekeeping() -> None:
    await bot.wait_until_ready()


@bot.event
async def on_ready() -> None:
    bot.add_view(TicketActionView())
    bot.add_view(TicketPanelView())
    bot.add_view(LeaveView())

    if not housekeeping.is_running():
        housekeeping.start()

    print(f"✅ {bot.user} is ready")


@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx: commands.Context) -> None:
    try:
        if ctx.channel.id != TICKET_SETUP_CHANNEL_ID:
            await send_temp_message(ctx.channel, "أمر التكت يعمل فقط في الروم المخصص له.")
            return

        embed = discord.Embed(
            title="مركز تذاكر BLS",
            description="اختر نوع التذكرة من القائمة بالأسفل وسيتم فتحها في القسم المناسب.",
            color=0x2F3136,
        )
        embed.set_footer(text="BLS Ticket System")
        await ctx.send(embed=embed, view=TicketPanelView())
    finally:
        await safe_delete_message(ctx.message)


@bot.command()
@commands.has_permissions(administrator=True)
async def setup_vacation(ctx: commands.Context) -> None:
    try:
        if ctx.channel.id != LEAVE_PANEL_CHANNEL_ID:
            await send_temp_message(ctx.channel, "أمر الإجازات يعمل فقط في الروم المخصص له.")
            return

        embed = discord.Embed(
            title="نظام الإجازات",
            description=(
                "رصيد الإجازة الشهري 14 يوم.\n"
                "عند بداية كل شهر يرجع الرصيد تلقائيًا.\n"
                "إذا كان عليك إنذار إداري فعال فلن تستطيع طلب إجازة."
            ),
            color=0x3498DB,
        )
        embed.set_footer(text="BLS Leave System")
        await ctx.send(embed=embed, view=LeaveView())
    finally:
        await safe_delete_message(ctx.message)


@bot.command(name="warn")
@commands.has_permissions(administrator=True)
async def warn_member(ctx: commands.Context, member: discord.Member, days: int, *, reason: str) -> None:
    try:
        if ctx.channel.id != WARNING_CHANNEL_ID:
            await send_temp_message(ctx.channel, "أمر الإنذارات يعمل فقط في روم الإنذارات.")
            return

        if days <= 0:
            await send_temp_message(ctx.channel, "مدة الإنذار يجب أن تكون أكبر من صفر.")
            return

        await add_warning(
            member=member,
            duration_days=days,
            reason=reason,
            issued_by=ctx.author,
            source="manual_warning",
        )
    finally:
        await safe_delete_message(ctx.message)


@bot.command(name="unwarn")
@commands.has_permissions(administrator=True)
async def unwarn_member(ctx: commands.Context, member: discord.Member, *, reason: str) -> None:
    try:
        if ctx.channel.id != WARNING_CHANNEL_ID:
            await send_temp_message(ctx.channel, "أمر سحب الإنذار يعمل فقط في روم الإنذارات.")
            return

        removed = await clear_all_warnings(
            member=member,
            removed_by=ctx.author,
            reason=reason,
            source="سحب مبكر",
        )

        if removed == 0:
            await send_temp_message(ctx.channel, "هذا العضو ليس عليه إنذارات فعالة.")
    finally:
        await safe_delete_message(ctx.message)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    await safe_delete_message(ctx.message)

    if isinstance(error, commands.MissingRequiredArgument):
        await send_temp_message(ctx.channel, "صيغة الأمر ناقصة.")
        return

    if isinstance(error, commands.BadArgument):
        await send_temp_message(ctx.channel, "تعذر قراءة بيانات الأمر. تأكد من المنشن والمدة.")
        return

    if isinstance(error, commands.CheckFailure):
        await send_temp_message(ctx.channel, "لا تملك صلاحية استخدام هذا الأمر.")
        return

    if isinstance(error, commands.CommandNotFound):
        return

    await send_temp_message(ctx.channel, "حدث خطأ غير متوقع أثناء تنفيذ الأمر.")


keep_alive()

if TOKEN:
    bot.run(TOKEN)
else:
    print("TOKEN environment variable is missing.")
