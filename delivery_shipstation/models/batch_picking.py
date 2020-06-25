# -*- coding: utf-8 -*-
##############################################################################
#
# Bista Solutions Pvt. Ltd
# Copyright (C) 2020 (https://www.bistasolutions.com)
#
##############################################################################
from odoo import api, fields, models, _
from PyPDF2 import PdfFileMerger, PdfFileReader, PdfFileWriter
import base64, os, tempfile


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    label_generated = fields.Boolean('Label Generated', default=False)

    def generate_label(self):
        """Generate picking labels individually and combined.
        """
        # status = self.picking_ids.mapped('state')
        for pick in self.picking_ids.filtered(lambda p: p.state == 'assigned'):
            pick.send_to_shipper()
        attachment_id, batch_file_name = self.get_attachment_pdf()
        self.label_generated = True
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=%s&field=datas&id=%s&filename=%s' % (
                'ir.attachment', attachment_id.id, batch_file_name),
            'target': 'new',
        }

    def pdf_page_merge(self, input_files, output_stream):
        input_streams = []
        try:
            # First open all the files, then produce the output file, and
            # finally close the input files. This is necessary because
            # the data isn't read from the input files until the write
            # operation.
            for input_file in input_files:
                input_streams.append(open(input_file, 'rb'))
            pdf_writer = PdfFileWriter()
            for reader in map(PdfFileReader, input_streams):
                # reader.getNumPages()
                for n in range(1):
                    pdf_writer.addPage(reader.getPage(n))
            with open(output_stream, 'wb') as fileobj:
                pdf_writer.write(fileobj)
                pdf_writer.close()
        finally:
            for f in input_streams:
                f.close()
            return output_stream

    # This is used for merged multiple files completly.
    # def merge_pdfs(self, input_pdfs, output_pdf):
    #     """Combine multiple pdfs to single pdf.
    #     Args:
    #         input_pdfs (list): List of path files.
    #         output_pdf (str): Output file.
    #
    #     """
    #     pdf_merger = PdfFileMerger()
    #     for path in input_pdfs:
    #         pdf_merger.append(path)
    #     with open(output_pdf, 'wb') as fileobj:
    #         pdf_merger.write(fileobj)
    #         pdf_merger.close()
    #     return output_pdf

    def get_attachment_pdf(self):
        """
        Create/Update PDF with all picking labels
        :return:
        """
        attachments = self.env['ir.attachment']
        attachments_ids = attachments.search(
            [('res_model', '=', 'stock.picking'), ('res_id', 'in', self.picking_ids.ids)])
        count = 1
        f2_name_list = []
        for rec in attachments_ids:
            file_name = rec.res_name.replace('/', '_') + '_' + str(count) + '.pdf'
            f2_name = os.path.join(tempfile.gettempdir(),
                                   file_name)
            f2_name_list.append(f2_name)
            pre_f = base64.b64decode(
                rec.datas)
            with open(f2_name, 'wb') as f1:
                f1.write(pre_f)
                f1.close()
            count += 1
        # Creating Single pdf
        batch_file_name = 'Label-%s.pdf' % self.name.replace('/', '-')
        f1_name = os.path.join(tempfile.gettempdir(), batch_file_name)
        with open(f1_name, 'wb') as f:
            f.write(b'')
            f.close()
        # output_pdf = self.merge_pdfs(f2_name_list, f1_name)
        output_pdf = self.pdf_page_merge(f2_name_list, f1_name)
        cf = open(output_pdf, 'rb')
        attachment_dict = {
            'name': batch_file_name,
            'datas': base64.encodestring(cf.read()),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary'
        }
        attachment_id = attachments.sudo().create(attachment_dict)
        # Remove Temp files form directory
        if output_pdf:
            os.remove(os.path.join(tempfile.gettempdir(), output_pdf))
        for f_name in f2_name_list:
            os.remove(os.path.join(tempfile.gettempdir(), f_name))
        return [attachment_id, batch_file_name]

    def cancel_tracking(self):
        """Cancel shipment tracking.
        """
        old_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.picking.batch'), ('res_id', '=', self.id)])
        for pick in self.picking_ids:
            pick.cancel_shipment()
        self.label_generated = False
        if old_attachment:
            old_attachment.sudo().unlink()
