from telegram.ext import Updater
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import CommandHandler
from telegram.ext import CallbackQueryHandler
import telegram as telega
import sqlite3 as sql
import datetime
import threading
import time
from enum import Enum


class KeyboardType(Enum):
    NONE = -1
    DEFAULT = 0
    TOP = 1
    STATS = 2

class StatType(Enum):
    ALL = 1
    ATTACK = 2
    HP = 3
    ACCURACY = 4
    AGILITY = 5
    ORATORY = 6

class PlayerStat:
    def __init__(self, cur, id=None):
        self.time = datetime.datetime.now()
        self.hp = 0
        self.attack = 0
        self.deff = 0
        self.power = 0
        self.accuracy = 0
        self.oratory = 0
        self.agility = 0
        self.raids = 0
        self.id = id
        try:
            cur.execute("CREATE TABLE IF NOT EXISTS userstats"
                        "(id INTEGER PRIMARY KEY,"
                        "time TEXT, hp INTEGER, attack  INTEGER, deff INTEGER, power INTEGER, accuracy INTEGER, "
                        "oratory INTEGER, agility INTEGER, raids INTEGER)")

            if self.id:
                self.get(cur)
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def put(self, cur):
        try:
            cur.execute("INSERT INTO userstats(time, hp, attack, deff, power, accuracy, oratory, agility, raids)"
                        " VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (self.time, self.hp, self.attack, self.deff, self.power, self.accuracy, self.oratory,
                         self.agility, self.raids))
            self.id = cur.lastrowid
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def get(self, cur):
        try:
            cur.execute("SELECT * FROM userstats WHERE id=?", (self.id,))
            self.time, self.hp, self.attack, self.deff, self.power, self.accuracy, self.oratory, self.agility, \
            self.raids = cur.fetchone()[1:10]
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
            return -1

    def update_stats(self, cur):
        try:
            cur.execute("""UPDATE userstats SET
                        time = ? , hp = ? , attack = ? , deff = ? , power = ? , accuracy = ? , oratory = ? ,
                        agility = ? WHERE id=?""",
                        (self.time, self.hp, self.attack, self.deff, self.power, self.accuracy,
                         self.oratory, self.agility, self.id))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
            return -1

    def update_raids(self, cur, id = None, time = None):
        try:
            cur.execute("""UPDATE userstats SET raids = ?  WHERE id=?""", (self.raids, self.id))
            if time is not None:
                cur.execute("INSERT INTO raids(id, time) VALUES(?, ?)", (id, time))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
            return -1

    def sum(self):
        return self.hp + self.attack + self.agility + self.accuracy + self.oratory

    def copy_stats(self, ps):
        self.time, self.hp, self.attack, self.deff, self.power, self.oratory, self.agility, self.accuracy, self.raids = \
            ps.time, ps.hp, ps.attack, ps.deff, ps.power, ps.oratory, ps.agility, ps.accuracy, ps.raids


class Player:
    def __init__(self, cur, setings=(None, -1, "", "", "", [None, None, None, None, None])):
        self.id, self.chatid, self.username, self.nic, self.squad, sids = setings
        if self.squad is None:
            self.squad = ""
        if self.nic is None:
            self.nic = ""
        if self.username is None:
            self.username = ""
        self.update_text(cur)
        self.stats = [PlayerStat(cur, i) if i is not None else None for i in sids]
        self.keyboard = KeyboardType.DEFAULT

    def get_stats(self, n):
        return self.stats[n]

    def set_stats(self, cur, ps: PlayerStat, n):
        if self.stats[n] is None:
            self.stats[n] = PlayerStat(cur)
            self.stats[n].copy_stats(ps)
            self.stats[n].put(cur)
            self.update_id(cur, n)
            return self.stats[n]
        else:
            self.stats[n].copy_stats(ps)
            self.stats[n].update_stats(cur)
            self.stats[n].update_raids(cur)
            self.update_id(cur, n)
            return self.stats[n]

    def update_id(self, cur, n):
        try:
            if n == 0:
                cur.execute("UPDATE users SET id1= ? WHERE id = ?", (self.stats[n].id, self.id))
            elif n == 1:
                cur.execute("UPDATE users SET id2= ? WHERE id = ?", (self.stats[n].id, self.id))
            elif n == 2:
                cur.execute("UPDATE users SET id3= ? WHERE id = ?", (self.stats[n].id, self.id))
            elif n == 3:
                cur.execute("UPDATE users SET lid= ? WHERE id = ?", (self.stats[n].id, self.id))
            elif n == 4:
                cur.execute("UPDATE users SET cid= ? WHERE id = ?", (self.stats[n].id, self.id))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def update_text(self, cur):
        try:
            cur.execute("UPDATE users SET username = ?, nic = ?, squad = ? WHERE id = ?",
                        (self.username, self.nic, self.squad, self.id))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def delete(self, cur):
        try:
            cur.execute("DELETE FROM users WHERE id=?", (self.id,))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
            return -1
        for st in self.stats:
            if st is not None:
                try:
                    cur.execute("DELETE FROM userstats WHERE id=?", (st.id,))
                except sql.Error as e:
                    print("Sql error occurred:", e.args[0])
                    return -1


class Bot:
    def __init__(self, database: str, token, bot_name: str):
        conn = None
        self.database = database
        self.bot_name = bot_name
        try:
            conn = sql.connect(database)
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users"
                    "(id INT, chatid INT, username TEXT, nic TEXT, squad TEXT, id1 INT, id2 INT, id3 INT, lid INT, cid INT)")
        cur.execute('CREATE TABLE IF NOT EXISTS squads (name TEXT, short TEXT, chatid INT)')
        cur.execute('CREATE TABLE IF NOT EXISTS masters (id INTEGER, name TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER)')
        cur.execute('CREATE TABLE IF NOT EXISTS raids (id INTEGER, time TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS blacklist (id INTEGER)')
        cur.execute("SELECT * FROM admins")
        self.admins = set(r[0] for r in cur.fetchall())
        cur.execute("SELECT * FROM blacklist")
        self.blacklist = set(r[0] for r in cur.fetchall())
        cur.execute("SELECT * FROM raids")
        self.raids = set((r[0], r[1]) for r in cur.fetchall())
        self.usersbyname = {}
        self.masters = {}
        self.users = {}
        self.squadnames = {}
        self.squadids = {}
        self.pinns = [] #(squad, pinn, time) or (squad) to unp #TODO написать реализацию
        self.keyboards = {}#TODO написать админские клавиатуры
        self.keyboards[KeyboardType.DEFAULT] = telega.ReplyKeyboardMarkup([[telega.KeyboardButton("💽 Моя статистика"),
                                                                            telega.KeyboardButton("🎖 Топы"), telega.KeyboardButton("👻 О боте")]], resize_keyboard = True)
        self.keyboards[KeyboardType.TOP] = telega.ReplyKeyboardMarkup([[telega.KeyboardButton("🏅 Рейтинг"), telega.KeyboardButton("⚔️ Дамагеры"),
                                                                        telega.KeyboardButton("❤️ Танки")],[telega.KeyboardButton("🤸🏽‍♂️ Ловкачи"), telega.KeyboardButton("🔫 Снайперы"),
                                                                        telega.KeyboardButton("🗣 Дипломаты")],
                                                                       [telega.KeyboardButton("📜 Полный список"), telega.KeyboardButton("🔙 Назад")]], resize_keyboard = True)
        self.state = KeyboardType.DEFAULT
        cur.execute("SELECT * FROM users")
        for r in cur.fetchall():
            #print(r)да почитай описание к боту, можно удобно следить за своими статами, бот в процессе допиливания, и будет расширен функционал))) но потом )))
            p = list(r[:5])
            p.append(list(r[5:]))
            self.usersbyname[r[2]] = r[0]
            self.users[r[0]] = Player(cur, p)

        cur.execute("SELECT * FROM masters")
        for r in cur.fetchall():
            if not r[0] in self.masters.keys():
                self.masters[r[0]] = set()
            self.masters[r[0]].add(r[1].lower())
        cur.execute("SELECT * FROM squads")
        for r in cur.fetchall():
            self.squadnames[r[1].lower()] = r[0]
            self.squadids[r[1].lower()] = r[2]
        self.updater = Updater(token=token)
        massage_handler = MessageHandler(Filters.text | Filters.command, self.handle_massage)
        start_handler = CommandHandler('start', self.handle_start)
        callback_handler = CallbackQueryHandler(callback=self.handle_callback)
        self.updater.dispatcher.add_handler(start_handler)
        self.updater.dispatcher.add_handler(massage_handler)
        self.updater.dispatcher.add_handler(callback_handler)
        self.updater.start_polling(clean=True)

    def handle_start(self, bot, update):
        message = update.message
        user = message.from_user
        if message.chat.type != "private":
            return
        if user.id in self.blacklist:
            bot.sendMessage(chat_id=message.chat_id, text="Не особо рад тебя видеть.\nУходи",
                            reply_markup = telega.ReplyKeyboardRemove())
            return
        elif user.id not in self.users.keys():
            bot.sendMessage(chat_id=message.chat_id, text="Привет, давай знакомиться.\nКидай мне форвард своих статов",
                            reply_markup = telega.ReplyKeyboardRemove())
            return
        self.users[user.id].keyboard = KeyboardType.DEFAULT
        bot.sendMessage(chat_id = message.chat_id, text = "Рад тебя видеть", reply_markup = self.keyboards[KeyboardType.DEFAULT])

    def add_admin(self, id):
        conn = sql.connect(self.database)
        if not id in self.admins:
            cur = conn.cursor()
            cur.execute("INSERT INTO admins(id) VALUES (?)", (id,))
            self.admins.add(id)
            conn.commit()

    def del_admin(self, id):
        conn = sql.connect(self.database)
        if id in self.admins:
            cur = conn.cursor()
            cur.execute("DELETE FROM admins WHERE id=?", (id,))
            self.admins.remove(id)
            conn.commit()
            return True
        return False

    def ban(self, cur, id, bann_him= True):
        if not id in self.blacklist:
            self.users[id].delete(cur)
            del (self.usersbyname[self.users[id].username])
            del (self.users[id])
            if(bann_him):
                cur.execute("INSERT INTO blacklist(id) VALUES (?)", (id,))
                self.blacklist.add(id)

    def unbun(self, id):
        conn = sql.connect(self.database)
        if id in self.blacklist:
            cur = conn.cursor()
            cur.execute("DELETE FROM blacklist WHERE id=?", (id,))
            self.blacklist.remove(id)
            conn.commit()
            return True
        return False

    def add_to_squad(self, cur, id, sq):
        self.users[id].squad = sq
        self.users[id].update_text(cur)

    def del_from_squad(self, cur, id):
        self.users[id].squad = ""
        self.users[id].update_text(cur)

    def add_master(self, cur, bot, id, adminid, sq):
        sq = sq.lower()
        if (sq not in self.squadnames.keys()):
            bot.sendMessage(chat_id = self.users[adminid].chatid, text = "Нет такого отряда")
            return
        if(adminid not in self.admins) and ((adminid not in self.masters.keys()) or (sq not in self.masters[adminid])):
            bot.sendMessage(chat_id=self.users[adminid].chatid, text="У вас нет на это прав. Возьмите их у Антона")
            return
        if(id in self.masters.keys()) and sq in self.masters[id]:
            bot.sendMessage(chat_id=self.users[adminid].chatid, text="Да он и так командир)")
            return
        cur.execute("INSERT into masters(id, name) VALUES (?, ?)", (id, sq))
        self.masters[id].add(sq)

    def add_squad(self, cur, bot, master, short, title,  id, chat_id):
        if id not in self.admins:
            bot.sendMessage(chat_id=self.users[id].chatid, text="Хм... А кто тебе сказал что ты так можешь?")
            return
        if master not in self.users.keys():
            bot.sendMessage(chat_id=chat_id, text="Пользователь @" + master + " ещё не зарегестрирован")
            return
        if (short in self.squadnames.keys()) or short == "none":
            bot.sendMessage(chat_id=chat_id, text="Краткое имя \"" + short + "\" уже занято")
            return
        r = (title, short, chat_id)
        cur.execute("INSERT into squads(name, short, chatid) VALUES(?, ?, ?)", r)
        self.masters[master] = set()
        self.squadnames[short] = r[0]
        self.squadids[short] = r[2]
        self.add_master(cur, bot, master, id, short)
        bot.sendMessage(chat_id=chat_id,
                        text="Создан отряд " + self.squadnames[short] + " aka " + short)

    def stat(self, bot, id, chat_id, n):
        player = self.users[id]
        ps = player.get_stats(n - 1)
        s = "<b>" + player.nic + "</b>\n"
        if player.squad != "":
            s += "Отряд: <b>" + self.squadnames[player.squad] + "</b>\n"
        s += "<b>От </b>" + str(ps.time) + "\n" \
                                      "<b>\nЗдоровье:          </b>" + str(ps.hp) + \
             "<b>\nУрон:                   </b>" + str(ps.attack) + \
             "<b>\nБроня:                 </b>" + str(ps.deff) + \
             "<b>\nСила:                   </b>" + str(ps.power) + \
             "<b>\nМеткость:           </b>" + str(ps.accuracy) + \
             "<b>\nХаризма:            </b>" + str(ps.oratory) + \
             "<b>\nЛовкость:           </b>" +  str(ps.agility) + \
             "<b>\n\nУспешные рейды:     </b>" + str(ps.raids)
        bot.sendMessage(chat_id=chat_id, text=s, parse_mode='HTML')

    def change(self, bot, id, chat_id, text):
        n = 4
        if len(text.split()) > 1 and text.split()[1].isdigit():
            n = int(text.split()[1])
            if n < 1 or n > 3 or self.users[id].stats[n - 1] is None:
                s = [str(i + 1) + ", " for i in range(3) if self.users[id].stats[i] is not None]
                s = "".join(s).strip(", ")
                if not s:
                    bot.sendMessage(chat_id=chat_id, text="У вас ещё нет сохранений")
                else:
                    bot.sendMessage(chat_id=chat_id, text="Доступны сохранения " + s)
                return
        if self.users[id].stats[n - 1] is None:
            bot.sendMessage(chat_id=chat_id, text="Пришлёшь мне ещё один форвард твоих статов?")
            return
        player = self.users[id]
        ops = player.get_stats(n - 1)
        player = self.users[id]
        ps = player.get_stats(4)
        s = "<b>" + player.nic + "</b>\n" \
            + "Прирост с: " + str(ops.time) + "\nПо: " + str(ps.time)
        if ps.hp - ops.hp:
            s += "<b>\nЗдоровье:          </b>" + str(ps.hp - ops.hp)
        if ps.attack - ops.attack:
            s += "<b>\nУрон:                   </b>" + str(ps.attack - ops.attack)
        if ps.deff - ops.deff:
            s += "<b>\nБроня:                 </b>" + str(ps.deff - ops.deff)
        if ps.power - ops.power:
            s += "<b>\nСила:                   </b>" + str(ps.power - ops.power)
        if ps.accuracy - ops.accuracy:
            s += "<b>\nМеткость:           </b>" + str(ps.accuracy - ops.accuracy)
        if ps.oratory - ops.oratory:
            s += "<b>\nКрасноречие:   </b>" + str(ps.oratory - ops.oratory)
        if ps.agility - ops.agility:
            s += "<b>\nЛовкость:           </b>" + str(ps.agility - ops.agility)
        if ps.raids - ops.raids:
            s += "<b>\n\nУспешные рейды:     </b>" + str(ps.raids - ops.raids)
        bot.sendMessage(chat_id=chat_id, text=s, parse_mode='HTML')

    def handle_forward(self, cur, bot, message):
        user = message.from_user
        player = self.users[user.id]
        text = message.text.strip(" \n\t")
        player.username = user.username
        self.usersbyname[user.username] = user.id
        tlines = text.split("\n")
        ps = PlayerStat(cur)
        n = -1
        nic = ""
        for i in range(1, len(tlines)):
            if tlines[i] and tlines[i][0] == '├' and tlines[i-1][0] == '├':
                n = i - 2
                break
        if n >= 0:
            nic = tlines[n][1:]
            ps.hp, hanger, ps.attack, ps.deff = [int("".join([c for c in x if c.isdigit()])) for x in tlines[n+2][tlines[n+2].find("/"):].split('|')]
            ps.power, ps.accuracy = [int("".join([c for c in x if c.isdigit()])) for x in tlines[n+3].split('|')]
            ps.oratory, ps.agility = [int("".join([c for c in x if c.isdigit()])) for x in tlines[n+4].split('|')]
        else:
            nl = 2  #МАГИЧЕСКАЯ КОНСТАНТА номер строки с ником игрока
            nic = tlines[nl].strip()
            for i in range(nl + 1, len(tlines)):
                if "Здоровье:" in tlines[i]:
                    ps.hp = int(tlines[i][tlines[i].find('/') + 1:])
                elif "Урон:" in tlines[i]:
                    ps.attack = int(tlines[i][tlines[i].find(':') + 2:])
                elif "Броня:" in tlines[i]:
                    ps.deff = int(tlines[i][tlines[i].find(':') + 2:])
                elif "Сила:" in tlines[i]:
                    ps.power = int(tlines[i][tlines[i].find(':') + 2:])
                elif "Меткость:" in tlines[i]:
                    ps.accuracy = int(tlines[i][tlines[i].find(':') + 2:])
                elif "Харизма:" in tlines[i]:
                    ps.oratory = int(tlines[i][tlines[i].find(':') + 2:])
                elif "Ловкость:" in tlines[i]:
                    ps.agility = int(tlines[i][tlines[i].find(':') + 2:])
        nic = nic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if player.nic == "":
            player.nic = nic
        elif player.nic != nic:
            bot.sendMessage(chat_id = player.chatid, text = "🤔 Раньше ты играл под другим ником.\nЕсли ты сменил игровой ник обратись к @ant_ant\nА инче не кидай мне чужой профиль!")
            return False
        ps.time = message.forward_date
        oldps = player.get_stats(4)
        ps.raids = 0
        if oldps is not None:
            player.set_stats(cur, oldps, 3)
            ps.raids = oldps.raids
        if "Рейд в " in tlines[-3]:
            date = message.forward_date
            time = tlines[-3].split()[-1]
            ddate = datetime.datetime(year=date.year, month=date.month, day=date.day, hour=int(time.split(':')[0]) % 24)
            if message.date - ddate < datetime.timedelta(milliseconds=10):
                ddate = ddate - datetime.timedelta(days=1)
            date = str(ddate).split('.')[0]
            if (user.id, date) not  in self.raids:
                self.raids.add( (user.id, date))
                ps.raids += 1
                ps.update_raids(cur, user.id, date)
                if player.squad in self.squadnames.keys():
                    text = "<b>"+ player.nic + "</b> aka @" +player.username + " отличился на рейде \n"+ date + "\n" + tlines[-2] + "\n" + tlines[-1]
                    #print(text)
                    bot.sendMessage(chat_id=self.squadids[player.squad], text= text, parse_mode='HTML')
                bot.sendMessage(chat_id=player.chatid, text="Засчитан успешный рейд", parse_mode='HTML')
        player.set_stats(cur, ps, 4)
        player.update_text(cur)
        bot.sendMessage(chat_id=player.chatid, text="Я занес твои результаты")
        return True

    def top(self, bot, id, username, chat_id, text, type:StatType, invisible = False, title = "", time = datetime.datetime.now()):
        arr = []
        s = ""
        if title:
            s = "<b>" + title + ":</b>"
        if type == StatType.ALL:
            if not s:
                s = "<b>Топ игроков:</b>"
            arr = [(pl.get_stats(4).sum(), pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in self.users.values()]
        elif type == StatType.HP:
            if not s:
                s = "<b>Топ танков:</b>"
            arr = [(pl.get_stats(4).hp, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in self.users.values()]
        elif type == StatType.ATTACK:
            if not s:
                s = "<b>Топ дамагеров:</b>"
            arr = [(pl.get_stats(4).attack, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in self.users.values()]
        elif type == StatType.ACCURACY:
            if not s:
                s = "<b>Топ снайперов:</b>"
            arr = [(pl.get_stats(4).accuracy, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in self.users.values()]
        elif type == StatType.AGILITY:
            if not s:
                s = "<b>Топ ловкачей:</b>"
            arr = [(pl.get_stats(4).agility, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in self.users.values()]
        elif type == StatType.ORATORY:
            if not s:
                s = "<b>Топ дипломатов:</b>"
            arr = [(pl.get_stats(4).oratory, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in self.users.values()]
        else:
            return
        arr.sort(reverse=True)
        sq = ""
        con1 = True
        cap = False
        admin = id in self.admins
        if text != "" and len(text.split()) != 1:
            sq = text.split()[1].lower()
            cap = id in self.masters.keys() and sq in self.masters[id]
            if self.users[id].squad != sq and not cap and not admin:
                bot.sendMessage(chat_id=chat_id, text="Похоже, это не ваш отряд", parse_mode='HTML')
                return
            if sq in self.squadnames.keys():
                con1 = False
                s  = s[:-5] + "</b> отряда <b>" + self.squadnames[sq] + ":</b>"
        i = 1
        sum = 0
        for val, name, nic, squad, lasttime in arr:
            lasttime = str(lasttime)
            lasttime = datetime.datetime.strptime(lasttime.split('.')[0], "%Y-%m-%d %H:%M:%S")
            if con1 or squad == sq:
                if (id in self.admins) or i <= 5 or (con1 and cap) or invisible or name == username:
                    if time - lasttime > datetime.timedelta(days = 7):
                        s += "\n" + str(i) + ') ***<a href = "t.me/' + name + '">' + nic + '</a>'
                    elif time - lasttime > datetime.timedelta(days = 3):
                        s += "\n" + str(i) + ') **<a href = "t.me/' + name + '">' + nic + '</a>'
                    elif time - lasttime > datetime.timedelta(hours = 36):
                        s += "\n" + str(i) + ') *<a href = "t.me/' + name + '">' + nic + '</a>'
                    else:
                        s += "\n" + str(i) + ') <a href = "t.me/'+ name + '">'+ nic + ' </a>'
                    if not invisible:
                        s+=": <b>" + str(val) + "</b>"
                    sum += val
                if i == 5 and not invisible:
                    s += "\n"
                i += 1
        if (id in self.admins or (con1 and cap)) and not invisible:
            s += "\n\nОбщий счет: " + str(sum)
        bot.sendMessage(chat_id=chat_id, text=s, parse_mode='HTML', disable_web_page_preview=True)

    def pin(self, bot, chat_id, text, uid):
        id = -1
        try:
            id = bot.sendMessage(chat_id = chat_id, text = text, parse_mode='HTML').message_id
        except:
            bot.sendMessage(chat_id= uid, text = "Не удалось доставить сообщение")
        time.sleep(1)
        try:
            bot.pinChatMessage(chat_id = chat_id, message_id = id)
        except:
            bot.sendMessage(chat_id = uid, text = "Я не смог запинить((")
            return
        bot.sendMessage(chat_id=uid, text="Готово\nСообщение в пине")

    def handle_command(self, cur, conn, bot, message):
        text = message.text
        user = message.from_user
        chat_id = message.chat_id
        text0 = text[:text.find(' ')] if text.find(' ') > 0 else text
        text0 = text0[:text0.find(self.bot_name)] if text0.find(self.bot_name) > 0 else text0
        # print(text0)
        if text0 == '/me':
            n = 5
            if len(text.split()) > 1 and text.split()[1].isdigit():
                n = int(text.split()[1])
                if n < 1 or n > 3 or self.users[user.id].stats[n - 1] is None:
                    s = [str(i + 1) + ", " for i in range(3) if self.users[user.id].stats[i] is not None]
                    s = "".join(s).strip(", ")
                    if not s:
                        bot.sendMessage(chat_id=chat_id, text="У вас ещё нет сохранений")
                    else:
                        bot.sendMessage(chat_id=chat_id, text="Доступны сохранения " + s)
                    return
            self.stat(bot, user.id, chat_id, n)
        elif text0 == '/change':
            self.change(bot, user.id, chat_id, text)
        elif text0 == '/stat':
            name = ""
            try:
                name = text.split()[1].strip("@")
            except ImportError:
                bot.sendMessage(chat_id=chat_id, text="А чьи статы-то?")
                return
            if name not in self.usersbyname.keys():
                # print(name)
                bot.sendMessage(chat_id=chat_id, text="Кто это вообще такой? Я его не знаю...")
                return
            if (user.id not in self.admins) and (
                    user.id not in self.masters.keys() or self.users[self.usersbyname[name]].squad not in self.masters[
                user.id]):
                bot.sendMessage(chat_id=chat_id, text="Любопытство не парок\nНо меру то знать надо...")
                return
            self.stat(bot, self.usersbyname[name], chat_id, 5)
        elif text0[:-1] == '/save' and 1 <= int(text0[-1]) <= 3:
            player = self.users[user.id]
            ps = player.get_stats(4)
            player.set_stats(cur, ps, int(text0[-1]) - 1)
            conn.commit()
            bot.sendMessage(chat_id=chat_id, text="Текущая статистика сохранена в ячейку №" + text0[-1])
        elif text0 == '/top':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ALL, time=message.date)
        elif text0 == '/rushtop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ATTACK, time=message.date)
        elif text0 == '/hptop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.HP, time=message.date)
        elif text0 == '/acctop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ACCURACY, time=message.date)
        elif text0 == '/agtop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.AGILITY, time=message.date)
        elif text0 == '/ortop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ORATORY, time=message.date)
        elif text0 == '/players':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ALL, invisible=True, title="Игроки",
                     time=message.date)
        elif text0 == "/new_squad" and (user.id in self.admins) and (
                        message.chat.type == "group" or message.chat.type == "supergroup"):
            short, master = "", ""
            try:
                short, master = text.split()[1:3]
            except ValueError:
                bot.sendMessage(id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            master = master.strip("@")
            if master not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="не знаю пользователя @" + master)
                return
            self.add_squad(cur, bot, self.usersbyname[master], short.lower(), message.chat.title, user.id, chat_id)
            conn.commit()
        elif text0 == "/make_master":
            short, master = "", ""
            try:
                short, master = text.split()[1:3]
            except ValueError:
                bot.sendMessage(id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            master = master.strip("@")
            if master not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="не знаю пользователя @" + master)
                return
            self.add_master(cur, bot, self.usersbyname[master], user.id, short)
            conn.commit()
        elif text0 == "/add":
            short, player = "", ""
            try:
                short, player = text.split()[1:3]
            except ValueError:
                bot.sendMessage(id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            player = player.strip("@")
            short = short.lower()
            if player not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="не знаю пользователя @" + player)
                return
            if short not in self.squadnames.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Не знаю такого отряда")
                return
            if (user.id not in self.admins) and (
                    user.id not in self.masters.keys() or short not in self.masters[user.id]):
                bot.sendMessage(chat_id=chat_id, text="У тебя нет такой власти")
                return
            self.add_to_squad(cur, self.usersbyname[player], short)
            bot.sendMessage(chat_id=chat_id,
                            text=("@" + player + " теперь в отряде <b>" + self.squadnames[short] + "</b>"),
                            parse_mode='HTML')
            conn.commit()
        elif text0 == "/echo":
            text = text + "\n "
            if len(text.split()) == 1:
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="сообщения-то и нехватает")
                return
            sq = text.split()[1].lower()
            k = min(text.find(" "), text.find("\n"))
            text = text[k + 1:]
            permision = user.id in self.admins
            if sq == "none":
                sq = ""
            elif sq in self.squadnames.keys():
                permision = permision or (user.id in self.masters.keys() and sq in self.masters[user.id])
                k = min(text.find(" "), text.find("\n"))
                text = text[k + 1:]
            else:
                sq = None
            if not permision:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Небеса не одарили вас столь великой властью\nМожешь рискнуть обратиться за "
                                     "ней к Антону")
                return
            for pl in self.users.values():
                if sq is None or sq == pl.squad:
                    try:
                        bot.sendMessage(chat_id=pl.chatid, text=text)
                    except:
                        bot.sendMessage(chat_id=self.users[user.id].chatid,
                                        text="Пользователь @" + pl.username + " отключил бота")
            bot.sendMessage(chat_id=self.users[user.id].chatid, text="Ваш зов был услышан")
        elif text0 == "/echo-s":
            text = text + "\n "
            if len(text.split()) <= 2:
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="сообщения-то и нехватает")
                return
            sq = text.split()[1].lower()
            k = min(text.find(" "), text.find("\n"))
            text = text[k + 1:]
            k = min(text.find(" "), text.find("\n"))
            text = text[k + 1:]
            if sq not in self.squadnames.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Весело наверное писать в несуществующий отряд")
                return
            if user.id not in self.admins and user.id not in self.masters.keys() and sq not in self.masters[user.id]:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Небеса не одарили вас столь великой властью\nМожешь рискнуть обратиться за "
                                     "ней к Антону")
                return
            bot.sendMessage(chat_id=self.squadids[sq], text=text, reply_markup = telega.ReplyKeyboardRemove())
            bot.sendMessage(chat_id=self.users[user.id].chatid, text="Ваш зов был услышан")
        elif text0 == "/pin":
            text = text + "\n "
            if len(text.split()) <= 3:
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="сообщения-то и нехватает")
                return
            sq = text.split()[1].lower()
            if sq not in self.squadnames.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Весело наверное писать в несуществующий отряд")
                return
            if user.id not in self.admins and user.id not in self.masters.keys() and sq not in self.masters[
                user.id]:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Небеса не одарили вас столь великой властью\nМожешь рискнуть обратиться за "
                                     "ней к Антону")
                return
            time_t = text.split()[2]
            ctime = datetime.datetime.now()
            delta = datetime.timedelta(0)
            try:
                if time_t.count(":") == 1:
                    new_time = datetime.datetime(year=ctime.year, month=ctime.month, day=ctime.day,
                                                 hour=int(time_t.split(':')[0]), minute=int(time_t.split(':')[1]))
                    delta = new_time - ctime
                    if (delta < datetime.timedelta(0)):
                        delta = (new_time + datetime.timedelta(days=1)) - ctime
                elif time_t.count(":") == 2:
                    new_time = datetime.datetime(year=ctime.year, month=ctime.month, day=ctime.day,
                                                 hour=int(time_t.split(':')[0]), minute=int(time_t.split(':')[1]),
                                                 second=int(time_t.split(':')[2]))
                    delta = new_time - ctime
                    if (delta < datetime.timedelta(0)):
                        delta = (new_time + datetime.timedelta(days=1)) - ctime
            except:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Не похоже это на время пина")
                return
            for i in range(3):
                k = min(text.find(" "), text.find("\n"))
                text = text[k + 1:]
            threading.Timer(delta.total_seconds(), self.pin,
                            kwargs={'bot': bot, 'chat_id': self.squadids[sq], 'text': text, 'uid': chat_id}).start()
        elif text0 == "/ban":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Великая сила - это великая ответственность\nРазве ты настолько ответственен?")
                return
            if len(text.split()) != 2:
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Неверный формат")
                return
            pl = text.split()[1].strip("@")
            if pl not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Не знаю такого")
                return
            self.ban(cur, self.usersbyname[pl])
            bot.sendMessage(chat_id=chat_id, text="Вы его больше не увидите")
            conn.commit()
        elif text0 == "/kick":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Великая сила - это великая ответственность\nРазве ты настолько ответственен?")
                return
            if len(text.split()) != 2:
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Неверный формат")
                return
            pl = text.split()[1].strip("@")
            if pl not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Не знаю такого")
                return
            self.ban(cur, self.usersbyname[pl], False)
            bot.sendMessage(chat_id=chat_id, text="Я выкинул его из списков")
            conn.commit()
        else:
            if message.chat.type == "private":
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Неизвестная команда... Сам придумал?")

    def start(self):
        self.updater.start_polling()

    def handle_massage(self, bot, update):
        message = update.message
        chat_id = message.chat_id
        user = message.from_user
        #print("!",  message.chat_id, user.username)
        if user.id in self.blacklist and message.chat.type == "private":
            bot.sendMessage(chat_id=chat_id, text="Прости, но тебе здесь не рады")
            return
        text = message.text.strip(" \n\t")
        conn = None
        cur = None
        try:
            conn = sql.connect(self.database)
            cur = conn.cursor()
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
        if (message.forward_from is not None) and (message.forward_from.id == 430930191) and ('🗣' in text and '❤️'in text and '🔥' in text and '⚔️' in text) and message.chat.type == "private":
            if user.id not in self.users.keys():
                if "Убежище 6" not in text:
                    bot.sendMessage(chat_id=chat_id, text="А ты фракцией не ошибся?")
                    return
                if message.date - message.forward_date > datetime.timedelta(minutes=2):
                    bot.sendMessage(chat_id=chat_id, text="А можно профиль посвежее?")
                    return
                self.users[user.id] = Player(cur)
                self.users[user.id].id = user.id
                self.users[user.id].chatid = chat_id
                self.usersbyname[user.username] = user.id
                try:
                    cur.execute("INSERT INTO users(id, chatid, username) VALUES(?, ?, ?)",
                                (user.id, chat_id, user.username))
                    if not self.handle_forward(cur, bot, message):
                        del(self.users[user.id])
                        del(self.usersbyname[user.username])
                        return
                except:
                    del (self.users[user.id])
                    del (self.usersbyname[user.username])
                    return
                conn.commit()
                self.users[user.id].keyboard = KeyboardType.DEFAULT
                bot.sendMessage(chat_id=chat_id, text="Я тебя запомнил", reply_markup = self.keyboards[KeyboardType.DEFAULT])
            elif self.handle_forward(cur, bot, message):
                conn.commit()
            return
        if user.id not in self.users.keys():
            if message.chat.type == "private":
                bot.sendMessage(chat_id=chat_id, text="Мы ещё не знакомы. Скинь мне форвард своих статов))", reply_markup = telega.ReplyKeyboardRemove())
            return
        if text[0] == '/':
            self.handle_command(cur,conn, bot, message)
            if message.chat.type == "private":
                bot.sendMessage(reply_markup = self.keyboards[self.users[user.id].keyboard])
        else:
            player = self.users[user.id]
            if message.chat.type == "private":
                if text == "🔙 Назад":
                    player.keyboard = KeyboardType.DEFAULT
                    bot.sendMessage(chat_id=chat_id, text="Добро пожаловать в <b>главное меню</b>",
                                    reply_markup=self.keyboards[player.keyboard], parse_mode='HTML')
                    return
                if player.keyboard == KeyboardType.DEFAULT:
                    if text == "👻 О боте":
                        self.info(bot, player)
                        return
                    elif text == "🎖 Топы":
                        player.keyboard = KeyboardType.TOP
                        bot.sendMessage(chat_id = chat_id, text = "Здесь ты можешь увидеть списки лучших игроков 6 убежища\n"
                                                                  "<i>* перед именем игрока говорят о том, что его профиль устарел, чем их меньше тем актуальнее данные</i>",
                                        reply_markup = self.keyboards[player.keyboard], parse_mode='HTML')
                        return
                    elif text == "💽 Моя статистика":
                        self.my_stat(bot, player)
                        return
                elif  player.keyboard == KeyboardType.TOP:
                    if text == "🏅 Рейтинг":
                        self.top(bot, user.id, user.username, chat_id, "", StatType.ALL, time=message.date)
                        return
                    if text == "⚔️ Дамагеры":
                        self.top(bot, user.id, user.username, chat_id, "", StatType.ATTACK, time=message.date)
                        return
                    if text == "❤️ Танки":
                        self.top(bot, user.id, user.username, chat_id, "", StatType.HP, time=message.date)
                        return
                    if text == "🤸🏽‍♂️ Ловкачи":
                        self.top(bot, user.id, user.username, chat_id, "", StatType.AGILITY, time=message.date)
                        return
                    if text == "🔫 Снайперы":
                        self.top(bot, user.id, user.username, chat_id, "", StatType.ACCURACY, time=message.date)
                        return
                    if text == "🗣 Дипломаты":
                        self.top(bot, user.id, user.username, chat_id, "", StatType.ORATORY, time=message.date)
                        return
                    if text == "📜 Полный список":
                        self.top(bot, user.id, user.username, chat_id, "", StatType.ALL, invisible=True, title="Игроки", time=message.date)
                        return
                bot.sendMessage(chat_id=chat_id, text="Это что-то странное🤔\nДумать об этом я конечно не буду 😝")

    def info(self, bot, player:Player):
        text = "Перед вами стат бот 6 убежища <i>и он крут😎</i>\nОзнакомиться с его командами вы можете по ссылке" \
               " http://telegra.ph/StatBot-Redizajn-09-30\nНо для вашего же удобства рекомендую пользоваться графическим интерфейсом\n" \
               "Бот создан во имя блага и процветания 6 убежища игроком @ant_ant\n" \
               "Так что если найдете в нем серьезные баги - пишите мне)\nЕсли есть желание помочь - можетье подкинуть" \
               " денег (https://qiwi.me/67f1c4c8-705c-4bb3-a8d3-a35717f63858) на поддержку бота или связаться со мной и записаться в группу альфа-тестеров\n" \
               "\n<i>Играйте, общайтесь, радуйтесь жизни! Вместе мы сильнейшая фракция в игре!</i>\n\n<i>P.S.: Графический интерфейс еще не завершен. Дальше будет лучше</i>"
        bot.sendMessage(chat_id = player.chatid, text=text,  parse_mode='HTML', disable_web_page_preview=True, reply_markup = self.keyboards[player.keyboard])

    def my_stat(self, bot, player: Player):
        self.stat(bot, player.id, player.chatid, 5)

    def handle_callback(self, bot, update):
        query = update.callback_query
        message = query.message
        data = query.data

if __name__ == "__main__":
    bot = Bot("***************","*************", "******")
    bot.start()
    print("admins:", bot.admins)
    print("squadnames:", bot.squadnames.keys())
    print("users", bot.usersbyname.keys())
