import telegram as telega
import sqlite3 as sql
import threading
import time
from enum import IntEnum
from ww6StatBotPlayer import Player


def power(player: Player):
    ps = player.stats[4]
    return ps.attack + ps.hp + ps.deff + ps.agility + 10


class PinOnlineKm:
    class PlayerStatus(IntEnum):
        SKIPPING = -1
        GOING = 0
        ONPLACE = 1
        UNKNOWN = -2

    def __init__(self, squads: dict, players: dict, bot: telega.Bot, database):
        self.bot = bot
        self.squads = squads
        self.players = players
        self.db = database
        self.users = {}
        self.ordered_kms = ['3', '7', '10', '12', '15', '19', '22', '29', '36']
        self.players_online = {}  # dictionary of pairs {'km':km, 'squad':squad, 'state':state)
        self.clear()
        self.messages = {}
        self.connections = {}
        self.copies = {}
        self.chat_messages = {}
        self.update_cooldown_state = False
        self.commit_cooldown_state = False
        self.update_planed = False
        self.commit_planed = False
        self.chats_to_update = set()
        self.users_to_add = {}  # same format as players_online
        self.users_to_delete = set()
        self._markup = [
            [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in self.ordered_kms[:3]],
            [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in self.ordered_kms[3:6]],
            [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in self.ordered_kms[6:]],
            [telega.InlineKeyboardButton(text="B пити 🏃", callback_data="going_pin"),
             telega.InlineKeyboardButton(text=" На месте 👊", callback_data="onplace_pin"),
             telega.InlineKeyboardButton(text="Ой все 🖕", callback_data="skipping_pin")]]
        conn = sql.connect(database)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS players_online(id INTEGER UNIQUE ON CONFLICT REPLACE, km TEXT, data TEXT)")
        conn.commit()
        self._upload(conn)

    def clear(self):
        self.players_unconfirmed = {sq: {km: [] for km in self.ordered_kms} for sq in
                                    self.squads.keys()}  # dictionary of
        # ids stored for each squad
        self.players_confirmed = {sq: {km: [] for km in self.ordered_kms} for sq in self.squads.keys()}
        self.players_skipping = {sq: {km: [] for km in self.ordered_kms} for sq in self.squads.keys()}
        self.powers_on_km_unconfirmed = {km: 0 for km in self.ordered_kms}
        self.powers_on_km_confirmed = {km: 0 for km in self.ordered_kms}
        self.powers_on_squad_unconfirmed = {sq: 0 for sq in self.squads.keys()}
        self.powers_on_squad_confirmed = {sq: 0 for sq in self.squads.keys()}

    def add(self, uid, km, squad, recount=True):
        print("add")
        if uid not in self.players.keys() or km not in self.ordered_kms or squad not in self.squads.keys():
            return True
        if uid in self.players_online.keys() and self.players_online[uid]['km'] == km \
                and self.players_online[uid]['squad'] == squad:
            return False
        self.players_online[uid] = {'km': km, 'squad': squad, 'state': self.PlayerStatus.GOING}
        self.users_to_add[uid] = self.players_online[uid]
        if recount:
            self.recount()
        self.commit()
        return True

    def change_status(self, uid, squad, status):
        print("change")
        if status == self.PlayerStatus.SKIPPING:
            if uid in self.players_online.keys() and self.players_online[uid]['state'] == status:
                self.delete(uid)
                return True
            self.players_online[uid] = {'km': self.ordered_kms[0], 'squad': squad, 'state': status}
            self.delete(uid, False)
        elif uid not in self.players_online.keys():
            return False
        else:
            self.players_online[uid]['state'] = status
        self.recount()
        self.commit()
        return True

    def delete(self, uid, recount=True):
        print("del")
        if uid in self.players_online.keys():
            del (self.players_online[uid])
        if recount:
            self.recount()
            self.users_to_delete.add(uid)
        self.commit()

    def commit(self):
        print("comm")
        del_list = self.users_to_delete.copy()
        add_list = self.users_to_add.copy()
        self.users_to_delete.clear()
        self.users_to_add.clear()
        conn = sql.connect(self.db)
        cur = conn.cursor()
        try:
            for uid in del_list:
                cur.execute('DELETE FROM players_online WHERE id = ?', (uid,))
            for uid, pl in add_list.items():
                cur.execute('INSERT INTO players_online(id, km, data) VALUES(?, ?, ?)',
                            (uid, pl['km'], '{} {}'.format(pl['squad'], str(pl['state'].value))))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def _upload(self, conn: sql.Connection):
        cur = conn.cursor()
        cur.execute('SELECT * from players_online')
        for row in cur.fetchall():
            sq, state = row[2].split()
            self.players_online[row[0]] = {'km': row[1], 'squad': sq, 'state': self.PlayerStatus(int(state))}

    def recount(self):
        print("rec")
        self.clear()
        for uid in list(self.players_online):
            if uid not in self.players.keys():
                self.delete(uid, recount=False)
                continue
            pl = self.players_online[uid]
            km, squad, state = pl['km'], pl['squad'], pl['state']
            pw = power(self.players[uid])
            if state == self.PlayerStatus.GOING:
                self.players_unconfirmed[squad][km].append(uid)
                self.powers_on_km_unconfirmed[km] += pw
                self.powers_on_squad_unconfirmed[squad] += pw
            elif state == self.PlayerStatus.ONPLACE:
                self.players_confirmed[squad][km].append(uid)
                self.powers_on_km_confirmed[km] += pw
                self.powers_on_squad_unconfirmed[squad] += pw
            elif state == self.PlayerStatus.SKIPPING:
                self.players_skipping[squad][km].append(uid)

    def pin(self, sq, admin: Player, chat_message=""):
        print("pin")
        admin_chat = admin.chatid
        if sq not in self.squads.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Не знаю отряда " + sq)
            return
        if admin_chat not in self.connections.keys():
            self.connect(admin_chat)
        self.chat_messages[sq] = chat_message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if self.squads[sq] in self.messages.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Пин уже в отряде " + sq)
            self.chats_to_update.add(self.squads[sq])
            self.update()
            return
        text = "#пинонлайн\n<b>{}</b>".format(chat_message[sq])
        id = self.bot.sendMessage(chat_id=self.squads[sq], text=text,
                                  reply_markup=telega.InlineKeyboardMarkup(self._markup), parse_mode='HTML').message_id
        self.messages[self.squads[sq]] = id
        try:
            self.bot.pinChatMessage(chat_id=self.squads[sq], message_id=id)
        except:
            self.bot.sendMessage(chat_id=admin_chat, text=("Не смог запинить в " + sq))
        self.bot.sendMessage(chat_id=admin_chat, text=("Опрос доставлен в " + sq))
        self.update()

    def _players_in_squad(self, squad):
        print("_pl")
        """returns confirmed, total number of players + confirmed, total power, string of usernames"""
        cpl = tpl = cpw = tpw = 0
        ulist = []
        for km, uonkm in list(self.players_confirmed[squad].items()):
            for uid in list(uonkm):
                if uid not in self.players.keys():
                    self.delete(uid, recount=False)
                    continue
                cpl += 1
                tpl += 1
                pl = self.players[uid]
                pw = power(pl)
                cpw += pw
                tpw += pw
                ulist.append('@' + pl.username)
        ulist.append('|')
        for km, uonkm in list(self.players_unconfirmed[squad].items()):
            for uid in list(uonkm):
                if uid not in self.players.keys():
                    self.delete(uid, recount=False)
                    continue
                tpl += 1
                pl = self.players[uid]
                tpw += power(pl)
                ulist.append('@' + pl.username)
        return cpl, tpl, cpw, tpw, " ".join(ulist)

    def text(self):
        print("text")
        s = "<b>Пины</b>\n{}\n<b>Силы на данный момент:</b>\n".format(
            "\n".join(["{}: <b>{}</b>".format(m[0], m[1]) for m in list(self.chat_messages)]))
        for sq in list(self.squads.keys()):
            cpl, tpl, cpw, tpw, text = self._players_in_squad(sq)
            s += "{}:<b>{}/{}</b>🕳 ({}/{}){}\n".format(sq, cpl, tpl, cpw, tpw, text)
        return s

    def copy_to(self, chat_id):
        text = self.text()
        id = self.bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML').message_id
        self.copies[chat_id] = id

    def connect(self, chat_id):
        markup = [[telega.InlineKeyboardButton(text="Закрыть пин", callback_data="offkm")]]
        text = self.text()
        id = self.bot.sendMessage(chat_id=chat_id, text=text,
                                  reply_markup=telega.InlineKeyboardMarkup(markup)).message_id
        self.connections[chat_id] = id

    """def update_chat(self, chat_id):
        sq = self.squabyid[chat_id]
        text = "#пинонлайн\n" + self.mes + "<b>" + self.chatm[sq] + "</b>" + "\n\nонлайн (" + str(
            len(self.names[sq])) + ")\n"
        for km in self.ordered_kms:
            l = [u for u in self.kms[km] if self.users[self.usersbyname[u]][0] == chat_id]
            if l != []:
                text += "<b>" + km + "км</b> (" + str(len(l)) + "): @" + " @".join(l) + "\n"
            else:
                text += "<b>" + km + "км</b> (0) ---\n"
        kms = [x for x in self.ordered_kms]
        markup = [[telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[:3]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[3:6]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[6:]]]
        try:
            self.bot.editMessageText(chat_id=chat_id, message_id=self.messages[chat_id], text=text,
                                     reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML')
        except:
            pass"""

    def unfreeze(self):
        self.cooldownstate = False

    def update(self):
        print("up")
        self.planUpdate = False
        if self.cooldownstate:
            if not self.planUpdate:
                threading.Timer(0.07, self.update).start()
                self.planUpdate = True
            return
        self.cooldownstate = True
        list = self.chats_to_update.copy()
        self.chats_to_update.clear()
        """for chat in list:
            self.update_chat(chat)
            time.sleep(1. / 100)"""
        markup = [[telega.InlineKeyboardButton(text="Закрыть пин", callback_data="offkm")]]
        text = self.text()
        for con in self.connections.items():
            try:
                self.bot.editMessageText(chat_id=con[0], message_id=con[1], text=text,
                                         reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML')
            except:
                pass
        for con in self.copies.items():
            try:
                self.bot.editMessageText(chat_id=con[0], message_id=con[1], text=text, parse_mode='HTML')
            except:
                pass
        threading.Timer(0.05, self.unfreeze).start()

    def close(self):
        for m in self.messages.items():
            try:
                self.bot.editMessageReplyMarkup(chat_id=m[0], message_id=m[1])
            except:
                pass
        self.update()
        for m in self.connections.items():
            try:
                self.bot.editMessageReplyMarkup(chat_id=m[0], message_id=m[1])
            except:
                pass
        conn = sql.connect(self.db)
        conn.execute('DROP TABLE players_online')
        conn.commit()
