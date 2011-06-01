"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
import email
from urwid import Text
from urwid import Edit
from urwid import Pile
from urwid import Columns
from urwid import AttrMap
from urwid import WidgetWrap
from urwid import ListBox
from urwid import SimpleListWalker
from datetime import datetime

import settings
from helper import shorten
from helper import pretty_datetime


class ThreadlineWidget(AttrMap):
    def __init__(self, tid, dbman):
        self.dbman = dbman
        self.thread = dbman.get_thread(tid)
        self.rebuild()
        AttrMap.__init__(self, self.columns, 'threadline', 'threadline_focus')

    def rebuild(self):
        cols = []
        datestring = pretty_datetime(self.thread.get_newest_date())
        self.date_w = AttrMap(Text(datestring), 'threadline_date')
        cols.append(('fixed', len(datestring), self.date_w))

        mailcountstring = "(%d)" % self.thread.get_total_messages()
        self.mailcount_w = AttrMap(Text(mailcountstring),
                                   'threadline_mailcount')
        cols.append(('fixed', len(mailcountstring), self.mailcount_w))

        tagsstring = " ".join(self.thread.get_tags())
        self.tags_w = AttrMap(Text(tagsstring), 'threadline_tags')
        if tagsstring:
            cols.append(('fixed', len(tagsstring), self.tags_w))

        authors = self.thread.get_authors() or '(None)'
        authorsstring = shorten(authors, settings.authors_maxlength)
        self.authors_w = AttrMap(Text(authorsstring), 'threadline_authors')
        cols.append(('fixed', len(authorsstring), self.authors_w))

        subjectstring = self.thread.get_subject()
        self.subject_w = AttrMap(Text(subjectstring, wrap='clip'),
                                 'threadline_subject')
        if subjectstring:
            cols.append(self.subject_w)

        self.columns = Columns(cols, dividechars=1)
        self.original_widget = self.columns

    def render(self, size, focus=False):
        if focus:
            self.date_w.set_attr_map({None: 'threadline_date_linefocus'})
            self.mailcount_w.set_attr_map({None:
                                           'threadline_mailcount_linefocus'})
            self.tags_w.set_attr_map({None: 'threadline_tags_linefocus'})
            self.authors_w.set_attr_map({None: 'threadline_authors_linefocus'})
            self.subject_w.set_attr_map({None: 'threadline_subject_linefocus'})
        else:
            self.date_w.set_attr_map({None: 'threadline_date'})
            self.mailcount_w.set_attr_map({None: 'threadline_mailcount'})
            self.tags_w.set_attr_map({None: 'threadline_tags'})
            self.authors_w.set_attr_map({None: 'threadline_authors'})
            self.subject_w.set_attr_map({None: 'threadline_subject'})
        return AttrMap.render(self, size, focus)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_thread(self):
        return self.thread


class BufferlineWidget(Text):
    def __init__(self, buffer):
        self.buffer = buffer
        Text.__init__(self, str(buffer), wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_buffer(self):
        return self.buffer


class TagWidget(Text):
    def __init__(self, tag):
        self.tag = tag
        Text.__init__(self, tag, wrap='clip')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_tag(self):
        return self.tag


class PromptWidget(AttrMap):
    def __init__(self, prefix, text='', completer=None):
        self.completer = completer
        leftpart = Text(prefix, align='left')
        self.editpart = Edit(edit_text=text)
        self.start_completion_pos = len(text)
        self.completion_results = None
        both = Columns(
            [
                ('fixed', len(prefix) + 1, leftpart),
                ('weight', 1, self.editpart),
            ])
        AttrMap.__init__(self, both, 'prompt', 'prompt')

    def set_input(self, txt):
        return self.editpart.set_edit_text(txt)

    def get_input(self):
        return self.editpart.get_edit_text()

    def keypress(self, size, key):
        if key in ['tab', 'shift tab']:
            if self.completer:
                pos = self.start_completion_pos
                original = self.editpart.edit_text[:pos]
                if not self.completion_results: #not already in completion mode
                    self.completion_results = [''] + self.completer.complete(original)
                    self.focus_in_clist = 1
                else:
                    if key == 'tab':
                        self.focus_in_clist += 1
                    else:
                        self.focus_in_clist -= 1
                if len(self.completion_results) > 1:
                    suffix = self.completion_results[self.focus_in_clist %
                                              len(self.completion_results)]
                    self.editpart.set_edit_text(original + suffix)
                    self.editpart.edit_pos += len(suffix)
                else:
                    self.editpart.set_edit_text(original + ' ')
                    self.editpart.edit_pos += 1
                    self.start_completion_pos = self.editpart.edit_pos
                    self.completion_results = None
        else:
            result = self.editpart.keypress(size, key)
            self.start_completion_pos = self.editpart.edit_pos
            self.completion_results = None
            return result


class MessageWidget(WidgetWrap):
    def __init__(self, message, even=False, folded=True):
        self.message = message
        if even:
            sumattr = 'messagesummary_even'
        else:
            sumattr = 'messagesummary_odd'

        self.sumw = MessageSummaryWidget(self.message)
        self.headerw = MessageHeaderWidget(self.message.get_email())
        self.bodyw = MessageBodyWidget(self.message.get_email())
        self.displayed_list = [AttrMap(self.sumw, sumattr)]
        if not folded:
            self.displayed_list.append(self.bodyw)
        self.body = Pile(self.displayed_list)
        WidgetWrap.__init__(self, self.body)

    def rebuild(self):
        self.body = Pile(self.displayed_list)
        self._w = self.body

    def toggle_header(self):
        if self.headerw in self.displayed_list:
            self.displayed_list.remove(self.headerw)
        else:
            self.displayed_list.insert(1, self.headerw)
        self.rebuild()

    def toggle_body(self):
        if self.bodyw in self.displayed_list:
            self.displayed_list.remove(self.bodyw)
        else:
            self.displayed_list.append(self.bodyw)
        self.sumw.toggle_folded()
        self.rebuild()

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == 'h':
            self.toggle_header()
        elif key == 'enter':
            self.toggle_body()
        else:
            return self.body.keypress(size, key)

    def get_message(self):
        return self.message

    def get_email(self):
        return self.message.get_email()


class MessageSummaryWidget(WidgetWrap):
    def __init__(self, message, folded=True):
        self.message = message
        self.folded = folded
        WidgetWrap.__init__(self, Text(str(self)))

    def __str__(self):
        prefix = "-"
        if self.folded:
            prefix = '+'
        return prefix + str(self.message)

    def toggle_folded(self):
        self.folded = not self.folded
        self._w = Text(str(self))

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageHeaderWidget(AttrMap):
    def __init__(self, eml):
        self.eml = eml
        headerlines = []
        for line in settings.displayed_headers:
            if line in eml:
                headerlines.append('%s:%s' % (line, eml.get(line)))
        headertxt = '\n'.join(headerlines)
        AttrMap.__init__(self, Text(headertxt), 'message_header')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MessageBodyWidget(AttrMap):
    def __init__(self, eml):
        self.eml = eml
        bodytxt = ''.join(email.iterators.body_line_iterator(self.eml))
        AttrMap.__init__(self, Text(bodytxt), 'message_body')

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
