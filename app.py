# -*- coding: utf-8 -*-

import telebot
from telebot import types
from pyexcel_xls import get_data
from StringIO import StringIO
from validate_email import validate_email
import pickle
from collections import defaultdict


def send_order(mail, order):
    pass

bot_store = {}


class BotWrapper(object):
    def __init__(self, token):
        self.token = token

    def _bot(self):
        global bot_store
        if self.token not in bot_store:
            bot_store[self.token] = telebot.TeleBot(self.token)
        return bot_store[self.token]

    def send_message(self, chat_id, msg, reply_markup, parse_mode):
        return self._bot().send_message(chat_id, msg, reply_markup=reply_markup, parse_mode=parse_mode)

    def edit_message_text(self, msg, chat_id, message_id, reply_markup, parse_mode):
        return self._bot().edit_message_text(msg, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup, parse_mode=parse_mode)

    def add_message_handler(self, f, commands=None, content_types=None, func=None, regexp=None):
        self._bot().add_message_handler(f, commands=commands, func=func, content_types=content_types, regexp=regexp)

    def add_callback_query_handler(self, f, func):
        self._bot().add_callback_query_handler(f, func=func)

    def polling(self):
        print self._bot()
        print self.token
        self._bot().polling()

    def get_file(self, file_id):
        return self._bot().get_file(file_id)

    def download_file(self, file_path):
        return self._bot().download_file(file_path)


def mk_inline_markup(command_list):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(cmd, callback_data=cmd) for cmd in command_list]
    for btn in btns:
        markup.row(btn)
    return markup


def btn(txt, callback_data):
    return types.InlineKeyboardButton(txt, callback_data=callback_data)


def BTN(txt, request_contact=None):
    return types.KeyboardButton(txt, request_contact=request_contact)


class Context(object):
    def __init__(self, bot):
        self.bot = bot
        self.chat_id = None
        self.views = {}
        self.current_view = None
        self.tmpdata = None
        self.bots = {}
        self.orders = []
        self.current_basket = None

    def send_message(self, msg, markup=None):
        if self.chat_id:
            return self.bot.send_message(self.chat_id, msg, reply_markup=markup, parse_mode='HTML')

    def edit_message(self, message_id, msg, markup=None):
        if self.chat_id:
            return self.bot.edit_message_text(msg, chat_id=self.chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')

    def process_message(self, message):
        if self.current_view:
            try:
                txt = message.text.encode('utf-8')
            except:
                try:
                    txt = message.contact.phone_number
                except:
                    pass

            self.current_view.process_message(txt)

    def process_callback(self, callback):
        if self.current_view:
            self.current_view.process_callback(callback)


class View(object):
    def __init__(self, ctx, editable=True):
        self.ctx = ctx
        self.editable = editable

    def process_message(self, message):
        pass

    def process_callback(self, callback):
        pass

    def activate(self):
        self.ctx.views = {}
        self.ctx.current_view = self
        self.render()

    def get_msg(self):
        return ""

    def get_markup(self):
        return None

    def render(self):
        if self not in self.ctx.views:
            msg = self.ctx.send_message(self.get_msg(), self.get_markup())
            if msg and self.editable:
                self.ctx.views[self] = msg.message_id
                print msg.message_id, self.ctx.views
        else:
            print 'edit'
            self.ctx.edit_message(self.ctx.views[self], self.get_msg(), self.get_markup())


class MenuItem(object):
    def __init__(self, data):
        self.name = data['name']
        self.description = data['desc']
        self.price = int(data['price'])
        self.img_id = data['img']
        self.active = bool(int(data['active']))
        self.cat = data['cat']
        self.subcat = data['subcat']


class ItemNode(View):
    def __init__(self, menu_item, id, ctx, menu):
        self.editable = True
        self.description = menu_item.description
        self.img = menu_item.img_id
        self.count = 0
        self.price = menu_item.price
        self.name = menu_item.name
        self.id = id
        self.ctx = ctx
        self.ordered = False
        self.menu = menu

    def get_btn_txt(self):
        res = str(self.price) + ' руб.'
        if self.count > 0:
            res += ' ' + str(self.count) + ' шт.'
        return res

    def get_add_callback(self):
        return 'menu_item:' + str(self.id) + ':add'

    def get_basket_callback(self):
        return 'menu_item:' + str(self.id) + ':basket'

    def sub(self):
        self.count -= 1
        self.render()

    def add(self):
        self.count += 1
        self.render()

    def get_markup(self):
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton(self.get_btn_txt(), callback_data=self.get_add_callback()))
        if self.count > 0:
            markup.row(types.InlineKeyboardButton('Добавить в корзину', callback_data=self.get_basket_callback()))
        return markup

    def get_total(self):
        return self.count * self.price

    def get_msg(self):
        return '<a href="' + self.img + '">' + self.name + '</a>\n' + self.description

    def process_callback(self, call):
        _id, action = call.data.split(':')[1:]
        if action == 'add':
            self.count += 1
            self.render()
        if action == 'basket':
            print 'got to basket'
            self.ordered = True
            self.menu.goto_basket(call)


class BasketNode(View):
    def __init__(self, menu):
        self.menu = menu
        self.chat_id = None
        self.message_id = None
        self.ctx = menu.ctx
        self.items = []
        self.item_ptr = 0
        self.editable = True
        self.ctx.current_basket = self

    def get_ordered_items(self):
        return filter(lambda i: i.ordered is True, self.menu.items.values())

    def activate(self):
        self.items = self.get_ordered_items()
        self.item_ptr = 0

    def current_item(self):
        return self.items[self.item_ptr]

    def inc(self):
        if self.item_ptr + 1 < len(self.items):
            self.item_ptr += 1
            self.render()

    def dec(self):
        if self.item_ptr - 1 > -1:
            self.item_ptr -= 1
            self.render()

    def add(self):
        self.current_item().add()
        self.render()

    def sub(self):
        if self.current_item().count > 0:
            self.current_item().sub()
            self.render()

    def get_total(self):
        return sum(i.get_total() for i in self.items)

    def __str__(self):
        res = ""
        for item in self.items:
            if item.count > 0:
                res += item.name.encode('utf-8') + " " + str(item.count) + "шт. " + str(self.current_item().get_total()) + ' руб\n'
        res += 'Итого: ' + str(self.get_total()) + 'руб.'
        return res

    def get_msg(self):
        if self.get_total() > 0:
            res = 'Корзина:' + '\n\n'
            res += self.current_item().get_msg().encode('utf-8') + '\n'
            res += str(self.current_item().price) + ' * ' + str(self.current_item().count) + ' = ' + str(self.current_item().get_total()) + ' руб'
            return res
        else:
            return 'В Корзине пусто'

    def process_callback(self, call):
        action = call.data.split(':')[-1]
        print action
        if action == '>':
            self.inc()
        elif action == '<':
            self.dec()
        elif action == '+':
            self.add()
        elif action == '-':
            self.sub()

    def get_markup(self):
        if self.get_total() > 0:
            markup = types.InlineKeyboardMarkup()
            markup.row(
                btn('-', 'basket:-'), 
                btn(str(self.current_item().count) + ' шт.', 'basket:cnt'), 
                btn('+', 'basket:+')
            )
            markup.row(btn('<', 'basket:<'), btn(str(self.item_ptr + 1) + '/' + str(len(self.items)), 'basket:ptr'), btn('>', 'basket:>'))
            markup.row(btn('Заказ на ' + str(self.get_total()) + ' р. Оформить?', 'link:delivery'))
            return markup
        else:
            return None


class MenuNode(View):
    def __init__(self, menu_items, ctx, links):
        self.ctx = ctx
        self.items = {}
        self.basket = BasketNode(self)
        self.links = links
        print self.basket
        cnt = 0
        for item in menu_items:
            _id = str(cnt)
            self.items[_id] = ItemNode(item, _id, self.ctx, self)
            cnt += 1

    def render(self):
        for item in self.items.values():
            item.render()

    def process_callback(self, call):  # route callback to item node
        data = call.data.encode('utf-8')
        _type = data.split(':')[0]
        if _type == 'menu_item':
            node_id = data.split(':')[1]
            if node_id in self.items:
                self.items[node_id].process_callback(call)
        elif _type == 'basket':
            self.basket.process_callback(call)
        elif _type == 'link':
            ll = data.split(':')[1]
            print ll
            if ll in self.links:
                self.links[ll].activate()

    def goto_basket(self, call):
        self.basket.activate()
        self.basket.render()


class Detail(object):
    def __init__(self, id, default_options=[], name='', value=None):
        self.id = id
        self.default_options = default_options
        self.name = name
        self.value = value

    def is_filled(self):
        return self.value is not None

    def validate(self, value):
        return True

    def txt(self):
        return str(self.value)


class TextDetail(Detail):
    pass


class TokenDetail(TextDetail):
    def validate(self, value):
        try:
            b = telebot.TeleBot(value)
            b.get_me()
        except:
            return False

        return True


class EmailDetail(TextDetail):
    def validate(self, value):
        return validate_email(value)


class FileDetail(Detail):
    def validate(self, value):
        return value is not None

    def txt(self):
        if self.value:
            return 'Заполнено'
        else:
            return 'Не заполнено'


class DetailsView(View):
    def __init__(self, ctx, details, next_view=None, main_view=None, final_message=""):
        self.ctx = ctx
        self.details = details
        self.ptr = 0
        self.editable = False
        self.filled = False
        self.final_message = final_message
        self.next_view = next_view
        self.main_view = main_view
        if not self.next_view:
            self.next_view = self

    def activate(self):
        self.filled = False
        for d in self.details:
            d.value = None
        self.ptr = 0
        super(DetailsView, self).activate()

    def finalize(self):
        pass

    def current(self):
        return self.details[self.ptr]

    def get_msg(self):
        if self.filled:
            res = self.final_message + '\n'
            for d in self.details:
                res += (d.name + ": " + d.txt() + '\n')
            return res
        else:
            res = 'Укажите ' + self.current().name
            if self.current().is_filled():
                res += ' ( Сейчас: ' + self.current().value + ' )'
            return res

    def get_markup(self):
        if not self.filled:
            markup = types.ReplyKeyboardMarkup()
            if self.current().is_filled() or isinstance(self.current(), FileDetail):
                markup.row(BTN('ОК'))
            if self.current().id == 'phone':
                markup.row(BTN('отправить номер', True))
            if len(self.current().default_options) > 0:
                markup.row(*[BTN(opt) for opt in self.current().default_options])
            if self.ptr > 0:
                markup.row(BTN('назад'))

            markup.row(BTN('главное меню'))

            return markup
        else:
            return None

    def next(self):
        if self.ptr + 1 < len(self.details):
            if self.current().is_filled():
                self.ptr += 1
            self.render()
        else:
            self.filled = True
            self.render()
            self.next_view.activate()
            self.finalize()

    def prev(self):
        if self.ptr > 0:
            self.ptr -= 1
            self.render()

    def process_message(self, cmd):
        print cmd
        if cmd == 'ОК':
            if self.current().is_filled():
                self.next()
            elif isinstance(self.current(), FileDetail):
                if self.current().validate(self.ctx.tmpdata):
                    self.current().value = self.ctx.tmpdata
                    self.ctx.tmpdata = None
                    self.next()
                else:
                    self.ctx.send_message('Неверный формат файла')
        elif cmd == 'назад':
            self.prev()
        elif cmd == 'главное меню':
            self.main_view.activate()
        else:
            if isinstance(self.current(), TextDetail):
                if self.current().validate(cmd):
                    self.current().value = cmd
                    self.next()
                else:
                    self.ctx.send_message('Неверный формат')


class OrderCreatorView(DetailsView):
    def finalize(self):
        res = str(self.ctx.current_basket) + '\n' + 'Доставка:' + '\n'
        for d in self.details:
            res += (d.name + ": " + d.txt() + '\n')

        # if self.ctx.email:
        #     send_order(self.ctx.email, res)
        self.ctx.orders.append(res)


class BotCreatorView(DetailsView):
    def finalize(self):
        dd = {}
        for d in self.details:
            dd[d.id] = d.value
        new_bot = MarketBot(dd['shop.token'], dd['shop.items'], MarketBotConvo)
        new_bot.email = dd['shop.email']
        self.ctx.bots[new_bot.token] = new_bot
        self.ctx.engine.save()
        global bot_store
        print bot_store
        new_bot.start()


class NavigationView(View):
    def __init__(self, ctx, links={}, msg=""):
        self.links = links
        self.ctx = ctx
        self.editable = False
        self.msg = msg

    def get_msg(self):
        return self.msg

    def get_markup(self):
        markup = types.ReplyKeyboardMarkup()
        markup.keyboard.append([{'text': key} for key in self.links.keys()])
        return markup

    def process_message(self, message):
        print message
        if message in self.links:
            self.links[message].activate()


class HistoryView(NavigationView):
    def get_msg(self):
        if len(self.ctx.orders) > 0:
            return '\n-----------\n'.join(self.ctx.orders)
        else:
            return 'История заказов пуста'


class InlineNavigationView(View):
    def __init__(self, ctx, links={}, msg=''):
        self.ctx = ctx
        self.links = links
        self.editable = True
        self.msg = msg

    def get_msg(self):
        return self.msg

    def get_markup(self):
        markup = types.InlineKeyboardMarkup(row_width=2)
        for k in self.links.keys():
            markup.row(btn(k, callback_data=k))
        return markup

    def process_callback(self, callback):
        cmd = callback.data.encode('utf-8')
        print cmd, self.links.keys()
        if cmd in self.links:
            self.links[cmd].activate()

    def add_child(self, cmd, ch_view):
        self.links[cmd] = ch_view


class MarketBotConvo(object):
    def __init__(self, engine, data, bot, chat_id):
        self.ctx = Context(bot)
        self.engine = engine
        self.ctx.chat_id = chat_id

        self.delivery_view = OrderCreatorView(self.ctx, [
            TextDetail('delivery_type', ['Доставка до дома', 'Самовывоз'], name='тип доставки'),
            TextDetail('address', name='Ваш адрес'),
            TextDetail('phone', name='Ваш телефон'),
            TextDetail('delivery_time', name='желаемое время доставки')
        ], final_message='Заказ сформирован!')

        self.menu_cat_view = InlineNavigationView(self.ctx, msg="Выберите категорию:")
        categories = defaultdict(set)
        for item in data:
            categories[item.cat].add(item)
        for category, items in categories.items():
            self.menu_cat_view.add_child(category.encode('utf-8'), MenuNode(list(items), self.ctx, links={"delivery": self.delivery_view}))


        # self.menu_view = MenuNode(data, self.ctx, links={"delivery": self.delivery_view})
        self.history_view = HistoryView(self.ctx)
        self.main_view = NavigationView(self.ctx, links={"Меню": self.menu_cat_view, "История": self.history_view}, msg="Главное меню")
        self.history_view.links = {"Главное меню": self.main_view}
        self.history_view.main_view = self.main_view
        self.delivery_view.next_view = self.main_view
        self.delivery_view.main_view = self.main_view

    def process_message(self, message):
        self.ctx.process_message(message)

    def process_callback(self, callback):
        self.ctx.process_callback(callback)

    def goto_main(self):
        self.main_view.activate()

    def process_file(self, doc):
        pass


class MainConvo(MarketBotConvo):
    def __init__(self, engine, data, bot, chat_id):
        self.ctx = Context(bot)
        self.ctx.engine = engine
        self.engine = engine
        self.ctx.chat_id = chat_id
        self.add_view = BotCreatorView(self.ctx, [
            TextDetail('shop.name', name='название магазина'),
            TokenDetail('shop.token', name='токен для телеграм бота'),
            EmailDetail('shop.email', name='email для приема заказов'),
            FileDetail('shop.items', name='файл с описанием товаров')
        ], final_message='Магазин создан!')
        self.main_view = NavigationView(self.ctx, links={"Добавить магазин": self.add_view, "Настройки": self.add_view}, msg="Главное меню")
        self.add_view.next_view = self.main_view
        self.add_view.main_view = self.main_view

    def process_file(self, doc):
        # try:
        fid = doc.document.file_id
        file_info = self.ctx.bot.get_file(fid)
        content = self.ctx.bot.download_file(file_info.file_path)
        io = StringIO(content)
        data = get_data(io)
        data = data.values()[0][1:]

        items = []
        for item in data:
            items.append(MenuItem({
                'id': item[0],
                'active': item[1],
                'cat': item[2],
                'subcat': item[3],
                'name': item[5],
                'desc': item[6],
                'price': item[12],
                'img': item[15]
            }))

        self.ctx.tmpdata = items



class MarketBot(object):
    def __init__(self, token, data, convo_type):
        self.token = token    
        self.data = data
        self.convo_type = convo_type
        self.convos = {}

    def _init_bot(self):
        self.bot = BotWrapper(self.token)
        self.bot.add_message_handler(self.goto_main, commands=['start'])
        self.bot.add_callback_query_handler(self.process_callback, func=lambda call: True)
        self.bot.add_message_handler(self.process_file, content_types=['document'])
        self.bot.add_message_handler(self.process_message, func=lambda message: True, content_types=['text', 'contact'])

    def get_convo(self, chat_id):
        if chat_id not in self.convos:
            self.convos[chat_id] = self.convo_type(self, self.data, self.bot, chat_id)
        return self.convos[chat_id]

    def goto_main(self, message):
        convo = self.get_convo(message.chat.id)
        convo.goto_main()

    def process_callback(self, callback):
        convo = self.get_convo(callback.message.chat.id)
        convo.process_callback(callback)

    def process_message(self, message):
        convo = self.get_convo(message.chat.id)
        convo.process_message(message)

    def process_file(self, doc):
        chat_id = doc.chat.id
        print chat_id
        convo = self.get_convo(chat_id)
        convo.process_file(doc)

    def start(self):
        self._init_bot()
        self.bot.polling()


class MasterBot(MarketBot):
    def save(self):
        pickle.dump(self, open(self.token, 'wb'))

    def start(self):
        self._init_bot()
        for convo in self.convos.values():
            for bot in convo.ctx.bots.values():
                bot.start()
        self.bot.polling()

try:
    mb = pickle.load(open("203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw", 'rb'))
except:
    mb = MasterBot(
        token="203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw",
        data=[],
        convo_type=MainConvo
    )
mb.save()
mb.start()

