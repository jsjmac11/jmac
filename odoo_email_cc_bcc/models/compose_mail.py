# -*- encoding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################

import base64
import datetime
import logging
import psycopg2
import threading
import re

from email.utils import formataddr
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.exceptions import Warning
from odoo import _, api, fields, models, registry, SUPERUSER_ID, tools
from odoo.tools.safe_eval import safe_eval
from odoo.tools import pycompat
import logging

from odoo.tools import pycompat, ustr
from odoo.tools.misc import clean_context, split_every
from odoo.tools.safe_eval import safe_eval
_logger = logging.getLogger(__name__)


class ResCompany(models.Model):

    _inherit = 'res.company'

    display_cc_recipients = fields.Boolean(
        string="Display Recipients Cc (Partners)", default=False)
    display_bcc_recipients = fields.Boolean(
        string="Display Recipients Bcc (Partners)", default=False)
    display_cc = fields.Boolean(string="Display Cc (Emails)", default=True)
    display_bcc = fields.Boolean(string="Display Bcc (Emails)", default=True)
    display_reply_to = fields.Boolean(string="Display Reply To")
    default_cc = fields.Char(
        'Default Cc (Emails)', help='Carbon copy message recipients (Emails)')
    default_bcc = fields.Char(
        'Default Bcc (Emails)',
        help='Blind carbon copy message recipients (Emails)')
    default_reply_to = fields.Char('Default Reply To')


class MailComposer(models.TransientModel):
    """ Generic message composition wizard. You may inherit from this wizard
        at model and view levels to provide specific features.

        The behavior of the wizard depends on the composition_mode field:
        - 'comment': post on a record. The wizard is pre-populated via \
        ``get_record_data``
        - 'mass_mail': wizard in mass mailing mode where the mail details can
            contain template placeholders that will be merged with actual data
            before being sent to each recipient.
    """
    _inherit = 'mail.compose.message'

    @api.model
    def get_default_cc_email(self):
        if self.env.user.company_id.display_cc:
            return self.env.user.company_id.default_cc
        return False

    @api.model
    def get_default_bcc_emails(self):
        if self.env.user.company_id.display_bcc:
            return self.env.user.company_id.default_bcc
        return False

    @api.model
    def get_default_reply_to(self):
        if self.env.user.company_id.display_reply_to:
            return self.env.user.company_id.default_reply_to
        return False

    email_bcc = fields.Char(
        'Bcc (Emails)', help='Blind carbon copy message (Emails)',
        default=get_default_bcc_emails)
    email_cc = fields.Char(
        'Cc (Emails)', help='Carbon copy message recipients (Emails)',
        default=get_default_cc_email)
    cc_recipient_ids = fields.Many2many(
        'res.partner', 'mail_compose_message_res_partner_cc_rel',
        'wizard_id', 'partner_id', string='Cc (Partners)')
    bcc_recipient_ids = fields.Many2many(
        'res.partner', 'mail_compose_message_res_partner_bcc_rel',
        'wizard_id', 'partner_id', string='Bcc (Partners)')
    display_cc = fields.Boolean(
        string="Display Cc",
        default=lambda self: self.env.user.company_id.display_cc,)
    display_bcc = fields.Boolean(
        string="Display Bcc",
        default=lambda self: self.env.user.company_id.display_bcc,)
    display_cc_recipients = fields.Boolean(
        string="Display Recipients Cc (Partners)",
        default=lambda self: self.env.user.company_id.display_cc_recipients,)
    display_bcc_recipients = fields.Boolean(
        string="Display Recipients Bcc (Partners)",
        default=lambda self: self.env.user.company_id.display_bcc_recipients)
    display_reply_to = fields.Boolean(
        string="Display Reply To",
        default=lambda self: self.env.user.company_id.display_reply_to,)
    email_to = fields.Text('To', help='Message recipients (emails)')
    reply_to = fields.Char(
        'Reply-To',
        help='Reply email address. Setting the reply_to bypasses the \
        automatic thread creation.', default=get_default_reply_to)

    def get_mail_values(self, res_ids):
        """Generate the values that will be used by send_mail to create mail_messages
        or mail_mails. """
        self.ensure_one()
        results = super(MailComposer, self).get_mail_values(res_ids)
        for res_id in res_ids:
            # static wizard (mail.message) values
            results[res_id].update({
                'email_bcc': self.email_bcc,
                'email_cc': self.email_cc,
                'cc_recipient_ids': self.cc_recipient_ids,
                'bcc_recipient_ids': self.bcc_recipient_ids,
                'reply_to': self.reply_to,
                'email_to': self.email_to,
            })
        return results

    def generate_email_for_composer(self, template_id, res_ids, fields=None):

        """ Call email_template.generate_email(), get fields relevant for
            mail.compose.message, transform email_cc and email_to into partner_ids """
        multi_mode = True
        if isinstance(res_ids, int):
            multi_mode = False
            res_ids = [res_ids]

        if fields is None:
            fields = ['subject', 'body_html', 'email_from', 'email_to', 'partner_to', 'email_cc',  'reply_to', 'attachment_ids', 'mail_server_id']
        returned_fields = fields + ['partner_ids', 'attachments']
        values = dict.fromkeys(res_ids, False)

        template_values = self.env['mail.template'].with_context(tpl_partners_only=False).browse(template_id).generate_email(res_ids, fields=fields)
        for res_id in res_ids:
            res_id_values = dict((field, template_values[res_id][field]) for field in returned_fields if template_values[res_id].get(field))
            res_id_values['body'] = res_id_values.pop('body_html', '')
            values[res_id] = res_id_values
        if self.email_cc and res_id_values.get('email_cc'):
            res_id_values['email_cc'] = res_id_values['email_cc'] + ',' + self.email_cc
        return multi_mode and values or values[res_ids[0]]

class Message(models.Model):
    """ Messages model: system notification (replacing res.log notifications),
        comments (OpenChatter discussion) and incoming emails. """
    _inherit = 'mail.message'

    email_bcc = fields.Char(
        'Bcc (Emails)',
        help='Blind carbon copy message (Emails)')
    email_cc = fields.Char(
        'Cc (Emails)', help='Carbon copy message recipients (Emails)')
    cc_recipient_ids = fields.Many2many(
        'res.partner', 'mail_message_res_partner_cc_rel',
        'message_id', 'partner_id', string='Cc (Partners)')
    bcc_recipient_ids = fields.Many2many(
        'res.partner', 'mail_message_res_partner_bcc_rel',
        'message_id', 'partner_id', string='Bcc (Partners)')
    email_to = fields.Text('To', help='Message recipients (emails)')

    def write(self, vals):
        res = super(Message, self).write(vals)
        notfi_list = []
        cc_n_bcc = []
        for record in self:
            for notfi in record.notification_ids:
                notfi_list.append(notfi.res_partner_id.id)
            for cc in record.cc_recipient_ids:
                cc_n_bcc.append(cc.id)
            for bcc in record.bcc_recipient_ids:
                cc_n_bcc.append(bcc.id)
            if str(record).split('(')[0] == 'mail.message':
                for re in cc_n_bcc:
                    if re not in notfi_list:
                        values = {'mail_message_id': record.id,
                                  'is_read': True,
                                  'notification_status': 'sent',
                                  'res_partner_id': re
                                  }
                        self.env['mail.notification'].sudo().create(values)
                        notfi_list.append(re)
        return res


class Partners(models.Model):

    _inherit = "res.partner"

    @api.model
    def _notify_prepare_email_values(self, message):
        # compute email references
        references = message.parent_id.message_id \
            if message.parent_id else False

        # custom values
        custom_values = dict()
        if message.res_id and message.model in self.env and hasattr(
                self.env[message.model], 'message_get_email_values'):
            custom_values = self.env[message.model].browse(
                message.res_id).message_get_email_values(message)
        mail_values = {
            'mail_message_id': message.id,
            'mail_server_id': message.mail_server_id.id,
            'auto_delete': self._context.get('mail_auto_delete', True),
            'references': references,
            'email_bcc': message.email_bcc,
            'email_cc': message.email_cc,
            'cc_recipient_ids': message.cc_recipient_ids,
            'bcc_recipient_ids': message.bcc_recipient_ids,
            'email_to': message.email_to,
            'reply_to': message.reply_to,
        }
        mail_values.update(custom_values)
        return mail_values


class Mail(models.Model):

    _inherit = "mail.mail"

    def _send(self, auto_commit=False, raise_exception=False, smtp_session=None):
        IrMailServer = self.env['ir.mail_server']
        IrAttachment = self.env['ir.attachment']
        for mail_id in self.ids:
            success_pids = []
            failure_type = None
            processing_pid = None
            mail = None
            try:
                mail = self.browse(mail_id)
                if mail.state != 'outgoing':
                    if mail.state != 'exception' and mail.auto_delete:
                        mail.sudo().unlink()
                    continue

                # remove attachments if user send the link with the access_token
                body = mail.body_html or ''
                attachments = mail.attachment_ids
                for link in re.findall(r'/web/(?:content|image)/([0-9]+)', body):
                    attachments = attachments - IrAttachment.browse(int(link))

                # load attachment binary data with a separate read(), as prefetching all
                # `datas` (binary field) could bloat the browse cache, triggerring
                # soft/hard mem limits with temporary data.
                attachments = [(a['name'], base64.b64decode(a['datas']), a['mimetype'])
                               for a in attachments.sudo().read(['name', 'datas', 'mimetype']) if a['datas'] is not False]

                # specific behavior to customize the send email for notified partners
                email_list = []
                cc_list = []
                bcc_list = []
                if mail.email_to:
                    email_list.append(mail._send_prepare_values())
                for partner in mail.recipient_ids:
                    values = mail._send_prepare_values(partner=partner)
                    values['partner_id'] = partner
                    email_list.append(values)
                for partner in mail.cc_recipient_ids:
                    cc_list += mail._send_prepare_values(
                        partner=partner).get('email_to')
                for partner in mail.bcc_recipient_ids:
                    bcc_list += mail._send_prepare_values(
                        partner=partner).get('email_to')

                # headers
                headers = {}
                ICP = self.env['ir.config_parameter'].sudo()
                bounce_alias = ICP.get_param("mail.bounce.alias")
                catchall_domain = ICP.get_param("mail.catchall.domain")
                if bounce_alias and catchall_domain:
                    if mail.mail_message_id.is_thread_message():
                        headers['Return-Path'] = '%s+%d-%s-%d@%s' % (bounce_alias, mail.id, mail.model, mail.res_id, catchall_domain)
                    else:
                        headers['Return-Path'] = '%s+%d@%s' % (bounce_alias, mail.id, catchall_domain)
                if mail.headers:
                    try:
                        headers.update(safe_eval(mail.headers))
                    except Exception:
                        pass

                # Writing on the mail object may fail (e.g. lock on user) which
                # would trigger a rollback *after* actually sending the email.
                # To avoid sending twice the same email, provoke the failure earlier
                mail.write({
                    'state': 'exception',
                    'failure_reason': _('Error without exception. Probably due do sending an email without computed recipients.'),
                })
                # Update notification in a transient exception state to avoid concurrent
                # update in case an email bounces while sending all emails related to current
                # mail record.
                notifs = self.env['mail.notification'].search([
                    ('notification_type', '=', 'email'),
                    ('mail_id', 'in', mail.ids),
                    ('notification_status', 'not in', ('sent', 'canceled'))
                ])
                if notifs:
                    notif_msg = _('Error without exception. Probably due do concurrent access update of notification records. Please see with an administrator.')
                    notifs.sudo().write({
                        'notification_status': 'exception',
                        'failure_type': 'UNKNOWN',
                        'failure_reason': notif_msg,
                    })
                    # `test_mail_bounce_during_send`, force immediate update to obtain the lock.
                    # see rev. 56596e5240ef920df14d99087451ce6f06ac6d36
                    notifs.flush(fnames=['notification_status', 'failure_type', 'failure_reason'], records=notifs)

                # build an RFC2822 email.message.Message object and send it without queuing
                res = None
                for email in email_list:
                    msg = IrMailServer.build_email(
                        email_from=mail.email_from,
                        email_to=email.get('email_to'),
                        subject=mail.subject,
                        body=email.get('body'),
                        body_alternative=email.get('body_alternative'),
                        email_cc=tools.email_split(mail.email_cc) + cc_list,
                        email_bcc=tools.email_split(mail.email_bcc) + bcc_list,
                        reply_to=mail.reply_to,
                        attachments=attachments,
                        message_id=mail.message_id,
                        references=mail.references,
                        object_id=mail.res_id and ('%s-%s' % (mail.res_id, mail.model)),
                        subtype='html',
                        subtype_alternative='plain',
                        headers=headers)
                    processing_pid = email.pop("partner_id", None)
                    try:
                        res = IrMailServer.send_email(
                            msg, mail_server_id=mail.mail_server_id.id, smtp_session=smtp_session)
                        if processing_pid:
                            success_pids.append(processing_pid)
                        processing_pid = None
                    except AssertionError as error:
                        if str(error) == IrMailServer.NO_VALID_RECIPIENT:
                            failure_type = "RECIPIENT"
                            # No valid recipient found for this particular
                            # mail item -> ignore error to avoid blocking
                            # delivery to next recipients, if any. If this is
                            # the only recipient, the mail will show as failed.
                            _logger.info("Ignoring invalid recipients for mail.mail %s: %s",
                                         mail.message_id, email.get('email_to'))
                        else:
                            raise
                if res:  # mail has been sent at least once, no major exception occured
                    mail.write({'state': 'sent', 'message_id': res, 'failure_reason': False})
                    _logger.info('Mail with ID %r and Message-Id %r successfully sent', mail.id, mail.message_id)
                    # /!\ can't use mail.state here, as mail.refresh() will cause an error
                    # see revid:odo@openerp.com-20120622152536-42b2s28lvdv3odyr in 6.1
                mail._postprocess_sent_message(success_pids=success_pids, failure_type=failure_type)
            except MemoryError:
                # prevent catching transient MemoryErrors, bubble up to notify user or abort cron job
                # instead of marking the mail as failed
                _logger.exception(
                    'MemoryError while processing mail with ID %r and Msg-Id %r. Consider raising the --limit-memory-hard startup option',
                    mail.id, mail.message_id)
                # mail status will stay on ongoing since transaction will be rollback
                raise
            except (psycopg2.Error, smtplib.SMTPServerDisconnected):
                # If an error with the database or SMTP session occurs, chances are that the cursor
                # or SMTP session are unusable, causing further errors when trying to save the state.
                _logger.exception(
                    'Exception while processing mail with ID %r and Msg-Id %r.',
                    mail.id, mail.message_id)
                raise
            except Exception as e:
                failure_reason = tools.ustr(e)
                _logger.exception('failed sending mail (id: %s) due to %s', mail.id, failure_reason)
                mail.write({'state': 'exception', 'failure_reason': failure_reason})
                mail._postprocess_sent_message(success_pids=success_pids, failure_reason=failure_reason, failure_type='UNKNOWN')
                if raise_exception:
                    if isinstance(e, (AssertionError, UnicodeEncodeError)):
                        if isinstance(e, UnicodeEncodeError):
                            value = "Invalid text: %s" % e.object
                        else:
                            # get the args of the original error, wrap into a value and throw a MailDeliveryException
                            # that is an except_orm, with name and value as arguments
                            value = '. '.join(e.args)
                        raise MailDeliveryException(_("Mail Delivery Failed"), value)
                    raise

            if auto_commit is True:
                self._cr.commit()
        return True

class Thread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, *,
                     body='', subject=None, message_type='notification',
                     email_from=None, author_id=None, parent_id=False,
                     subtype_id=False, subtype=None, partner_ids=None, channel_ids=None,
                     attachments=None, attachment_ids=None,
                     add_sign=True, record_name=False,
                     **kwargs):
        """ Post a new message in an existing thread, returning the new
            mail.message ID.
            :param str body: body of the message, usually raw HTML that will
                be sanitized
            :param str subject: subject of the message
            :param str message_type: see mail_message.message_type field. Can be anything but
                user_notification, reserved for message_notify
            :param int parent_id: handle thread formation
            :param int subtype_id: subtype_id of the message, mainly use fore
                followers mechanism
            :param int subtype: xmlid that will be used to compute subtype_id
                if subtype_id is not given.
            :param list(int) partner_ids: partner_ids to notify
            :param list(int) channel_ids: channel_ids to notify
            :param list(tuple(str,str), tuple(str,str, dict) or int) attachments : list of attachment tuples in the form
                ``(name,content)`` or ``(name,content, info)``, where content is NOT base64 encoded
            :param list id attachment_ids: list of existing attachement to link to this message
                -Should only be setted by chatter
                -Attachement object attached to mail.compose.message(0) will be attached
                    to the related document.
            Extra keyword arguments will be used as default column values for the
            new mail.message record.
            :return int: ID of newly created mail.message
        """
        self.ensure_one()  # should always be posted on a record, use message_notify if no record
        # split message additional values from notify additional values
        msg_kwargs = dict((key, val) for key, val in kwargs.items() if key in self.env['mail.message']._fields)
        notif_kwargs = dict((key, val) for key, val in kwargs.items() if key not in msg_kwargs)

        if self._name == 'mail.thread' or not self.id or message_type == 'user_notification':
            raise ValueError('message_post should only be call to post message on record. Use message_notify instead')

        if 'model' in msg_kwargs or 'res_id' in msg_kwargs:
            raise ValueError(
                "message_post doesn't support model and res_id parameters anymore. Please call message_post on record")

        self = self.with_lang()  # add lang to context imediatly since it will be usefull in various flows latter.

        # Explicit access rights check, because display_name is computed as sudo.
        self.check_access_rights('read')
        self.check_access_rule('read')
        record_name = record_name or self.display_name

        partner_ids = set(partner_ids or [])
        channel_ids = set(channel_ids or [])

        if any(not isinstance(pc_id, int) for pc_id in partner_ids | channel_ids):
            raise ValueError('message_post partner_ids and channel_ids must be integer list, not commands')

        # Find the message's author
        author_info = self._message_compute_author(author_id, email_from, raise_exception=True)
        author_id, email_from = author_info['author_id'], author_info['email_from']

        if not subtype_id:
            subtype = subtype or 'mt_note'
            if '.' not in subtype:
                subtype = 'mail.%s' % subtype
            subtype_id = self.env['ir.model.data'].xmlid_to_res_id(subtype)

        # automatically subscribe recipients if asked to
        if self._context.get('mail_post_autofollow') and partner_ids:
            self.message_subscribe(list(partner_ids))

        MailMessage_sudo = self.env['mail.message'].sudo()
        if self._mail_flat_thread and not parent_id:
            parent_message = MailMessage_sudo.search(
                [('res_id', '=', self.id), ('model', '=', self._name), ('message_type', '!=', 'user_notification')],
                order="id ASC", limit=1)
            # parent_message searched in sudo for performance, only used for id.
            # Note that with sudo we will match message with internal subtypes.
            parent_id = parent_message.id if parent_message else False
        elif parent_id:
            old_parent_id = parent_id
            parent_message = MailMessage_sudo.search([('id', '=', parent_id), ('parent_id', '!=', False)], limit=1)
            # avoid loops when finding ancestors
            processed_list = []
            if parent_message:
                new_parent_id = parent_message.parent_id and parent_message.parent_id.id
                while (new_parent_id and new_parent_id not in processed_list):
                    processed_list.append(new_parent_id)
                    parent_message = parent_message.parent_id
                parent_id = parent_message.id

        cc_partner_ids = set()
        cc_recipient_ids = kwargs.pop('cc_recipient_ids', [])
        for partner_id in cc_recipient_ids:
            if isinstance(partner_id, (list, tuple)) and partner_id[0] == 4 \
                    and len(partner_id) == 2:
                cc_partner_ids.add(partner_id[1])
            if isinstance(partner_id, (list, tuple)) and partner_id[0] == 6 \
                    and len(partner_id) == 3:
                cc_partner_ids |= set(partner_id[2])
            else:
                pass
        bcc_partner_ids = set()
        bcc_recipient_ids = kwargs.pop('bcc_recipient_ids', [])
        for partner_id in bcc_recipient_ids:
            if isinstance(partner_id, (list, tuple)) and partner_id[0] == 4 and len(partner_id) == 2:
                bcc_partner_ids.add(partner_id[1])
            if isinstance(partner_id, (list, tuple)) and partner_id[0] == 6 and len(partner_id) == 3:
                bcc_partner_ids |= set(partner_id[2])
            else:
                pass

        values = dict(msg_kwargs)
        values.update({
            'author_id': author_id,
            'email_from': email_from,
            'model': self._name,
            'res_id': self.id,
            'body': body,
            'subject': subject or False,
            'message_type': message_type,
            'parent_id': parent_id,
            'subtype_id': subtype_id,
            'partner_ids': partner_ids,
            'channel_ids': channel_ids,
            'add_sign': add_sign,
            'record_name': record_name,
        })
        attachments = attachments or []
        attachment_ids = attachment_ids or []
        attachement_values = self._message_post_process_attachments(attachments, attachment_ids, values)
        values.update(attachement_values)  # attachement_ids, [body]

        new_message = self._message_create(values)

        # Set main attachment field if necessary
        self._message_set_main_attachment_id(values['attachment_ids'])

        if values['author_id'] and values['message_type'] != 'notification' and not self._context.get(
                'mail_create_nosubscribe'):
            self._message_subscribe([values['author_id']])

        self._message_post_after_hook(new_message, values)
        self._notify_thread(new_message, values, **notif_kwargs)
        return new_message

    def _notify_record_by_email(self, message, recipients_data, msg_vals=None,
                                model_description=False, mail_auto_delete=True, check_existing=False,
                                force_send=True, send_after_commit=True,
                                **kwargs):
        """ Method to send email linked to notified messages.

        :param message: mail.message record to notify;
        :param recipients_data: see ``_notify_thread``;
        :param msg_vals: see ``_notify_thread``;

        :param model_description: model description used in email notification process
          (computed if not given);
        :param mail_auto_delete: delete notification emails once sent;
        :param check_existing: check for existing notifications to update based on
          mailed recipient, otherwise create new notifications;

        :param force_send: send emails directly instead of using queue;
        :param send_after_commit: if force_send, tells whether to send emails after
          the transaction has been committed using a post-commit hook;
        """
        partners_data = [r for r in recipients_data['partners'] if r['notif'] == 'email']
        if not partners_data:
            return True

        model = msg_vals.get('model') if msg_vals else message.model
        model_name = model_description or (self.with_lang().env['ir.model']._get(model).display_name if model else False) # one query for display name
        recipients_groups_data = self._notify_classify_recipients(partners_data, model_name, msg_vals=msg_vals)

        if not recipients_groups_data:
            return True
        force_send = self.env.context.get('mail_notify_force_send', force_send)

        template_values = self._notify_prepare_template_context(message, msg_vals, model_description=model_description) # 10 queries

        email_layout_xmlid = msg_vals.get('email_layout_xmlid') if msg_vals else message.email_layout_xmlid
        template_xmlid = email_layout_xmlid if email_layout_xmlid else 'mail.message_notification_email'
        try:
            base_template = self.env.ref(template_xmlid, raise_if_not_found=True).with_context(lang=template_values['lang']) # 1 query
        except ValueError:
            _logger.warning('QWeb template %s not found when sending notification emails. Sending without layouting.' % (template_xmlid))
            base_template = False

        mail_subject = message.subject or (message.record_name and 'Re: %s' % message.record_name) # in cache, no queries
        # prepare notification mail values
        base_mail_values = {
            'mail_message_id': message.id,
            'mail_server_id': message.mail_server_id.id, # 2 query, check acces + read, may be useless, Falsy, when will it be used?
            'auto_delete': mail_auto_delete,
            # due to ir.rule, user have no right to access parent message if message is not published
            'references': message.parent_id.sudo().message_id if message.parent_id else False,
            'subject': mail_subject,
        }
        base_mail_values = self._notify_by_email_add_values(base_mail_values)

        Mail = self.env['mail.mail'].sudo()
        emails = self.env['mail.mail'].sudo()

        # loop on groups (customer, portal, user,  ... + model specific like group_sale_salesman)
        notif_create_values = []
        recipients_max = 50
        for recipients_group_data in recipients_groups_data:
            # generate notification email content
            recipients_ids = recipients_group_data.pop('recipients')
            render_values = {**template_values, **recipients_group_data}
            # {company, is_discussion, lang, message, model_description, record, record_name, signature, subtype, tracking_values, website_url}
            # {actions, button_access, has_button_access, recipients}

            if base_template:
                mail_body = base_template.render(render_values, engine='ir.qweb', minimal_qcontext=True)
            else:
                mail_body = message.body
            mail_body = self._replace_local_links(mail_body)

            # create email
            for recipients_ids_chunk in split_every(recipients_max, recipients_ids):
                recipient_values = self._notify_email_recipient_values(recipients_ids_chunk)
                email_to = recipient_values['email_to']
                recipient_ids = recipient_values['recipient_ids']

                create_values = {
                    'body_html': mail_body,
                    'subject': mail_subject,
                    'recipient_ids': [(4, pid) for pid in recipient_ids],
                    'email_cc': msg_vals.get('email_cc')
                }
                if email_to:
                    create_values['email_to'] = email_to
                create_values.update(base_mail_values)  # mail_message_id, mail_server_id, auto_delete, references, headers
                email = Mail.create(create_values)

                if email and recipient_ids:
                    tocreate_recipient_ids = list(recipient_ids)
                    if check_existing:
                        existing_notifications = self.env['mail.notification'].sudo().search([
                            ('mail_message_id', '=', message.id),
                            ('notification_type', '=', 'email'),
                            ('res_partner_id', 'in', tocreate_recipient_ids)
                        ])
                        if existing_notifications:
                            tocreate_recipient_ids = [rid for rid in recipient_ids if rid not in existing_notifications.mapped('res_partner_id.id')]
                            existing_notifications.write({
                                'notification_status': 'ready',
                                'mail_id': email.id,
                            })
                    notif_create_values += [{
                        'mail_message_id': message.id,
                        'res_partner_id': recipient_id,
                        'notification_type': 'email',
                        'mail_id': email.id,
                        'is_read': True,  # discard Inbox notification
                        'notification_status': 'ready',
                    } for recipient_id in tocreate_recipient_ids]
                emails |= email

        if notif_create_values:
            self.env['mail.notification'].sudo().create(notif_create_values)

        # NOTE:
        #   1. for more than 50 followers, use the queue system
        #   2. do not send emails immediately if the registry is not loaded,
        #      to prevent sending email during a simple update of the database
        #      using the command-line.
        test_mode = getattr(threading.currentThread(), 'testing', False)
        if force_send and len(emails) < recipients_max and (not self.pool._init or test_mode):
            # unless asked specifically, send emails after the transaction to
            # avoid side effects due to emails being sent while the transaction fails
            if not test_mode and send_after_commit:
                email_ids = emails.ids
                dbname = self.env.cr.dbname
                _context = self._context
                def send_notifications():
                    db_registry = registry(dbname)
                    with api.Environment.manage(), db_registry.cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, _context)
                        env['mail.mail'].browse(email_ids).send()
                self._cr.after('commit', send_notifications)
            else:
                emails.send()

        return True