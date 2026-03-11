import fitz  # PyMuPDF
import os
from datetime import datetime
from decimal import Decimal

class PDFOfferService:
    def __init__(self, output_dir: str = "static/offers"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def generate_offer_pdf(self, offer_data: dict) -> str:
        """
        Generates a PDF for the customer offer.
        Returns the path to the generated file.
        """
        filename = f"offer_{offer_data['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        # Create a new PDF
        doc = fitz.open()
        page = doc.new_page()
        
        # Load standard Turkish-capable fonts (Arial exists on Windows and most systems natively)
        font_path = "C:/Windows/Fonts/arial.ttf"
        font_bold_path = "C:/Windows/Fonts/arialbd.ttf"
        
        # Determine if we successfully loaded them
        has_local_fonts = os.path.exists(font_path) and os.path.exists(font_bold_path)
        if has_local_fonts:
            page.insert_font(fontname="arial_tr", fontfile=font_path)
            page.insert_font(fontname="arial_tr_bold", fontfile=font_bold_path)
            f_regular = "arial_tr"
            f_bold = "arial_tr_bold"
        else:
            f_regular = "helv"
            f_bold = "helv-bold"

        # Insert Logo if exists
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo.png")
        y = 50
        if os.path.exists(logo_path):
            rect = fitz.Rect(50, 40, 130, 130) # 80x80 square-ish bounding box
            page.insert_image(rect, filename=logo_path)
            
            # Position the Title next to the logo or below it
            page.insert_text((150, 70), "PERGEFOOD ERP - FİYAT TEKLİFİ", fontsize=16, color=(0, 0, 0), fontname=f_bold)
            page.insert_text((150, 90), f"Müşteri: {offer_data['customer_name']}", fontsize=12, fontname=f_regular)
            page.insert_text((400, 90), f"Tarih: {offer_data['date']}", fontsize=12, fontname=f_regular)
            y = 150
        else:
            page.insert_text((50, y), "PERGEFOOD ERP - FİYAT TEKLİFİ", fontsize=16, color=(0, 0, 0), fontname=f_bold)
            y += 40
            page.insert_text((50, y), f"Müşteri: {offer_data['customer_name']}", fontsize=12, fontname=f_regular)
            page.insert_text((400, y), f"Tarih: {offer_data['date']}", fontsize=12, fontname=f_regular)
            y += 40
        
        # Header for the table
        page.insert_text((50, y), "Ürün", fontsize=10, fontname=f_bold)
        page.insert_text((250, y), "Miktar", fontsize=10, fontname=f_bold)
        page.insert_text((350, y), "Birim Fiyat", fontsize=10, fontname=f_bold)
        page.insert_text((450, y), "Toplam", fontsize=10, fontname=f_bold)
        y += 20
        page.draw_line((50, y-5), (550, y-5))
        
        for item in offer_data['items']:
            page.insert_text((50, y), str(item['product_name'])[:30], fontsize=10, fontname=f_regular)
            page.insert_text((250, y), str(item['quantity']), fontsize=10, fontname=f_regular)
            page.insert_text((350, y), f"TL {float(item['unit_price']):.2f}", fontsize=10, fontname=f_regular)
            page.insert_text((450, y), f"TL {float(item['total_price']):.2f}", fontsize=10, fontname=f_regular)
            y += 20
            
            if y > 750:  # Simple page break logic
                page = doc.new_page()
                if has_local_fonts:
                    page.insert_font(fontname="arial_tr", fontfile=font_path)
                    page.insert_font(fontname="arial_tr_bold", fontfile=font_bold_path)
                y = 50

        y += 20
        page.draw_line((50, y-5), (550, y-5))
        page.insert_text((350, y), "Nakliye:", fontsize=10, fontname=f_regular)
        page.insert_text((450, y), f"TL {float(offer_data['shipping_cost']):.2f}", fontsize=10, fontname=f_regular)
        y += 20
        page.insert_text((350, y), "GENEL TOPLAM:", fontsize=12, fontname=f_bold)
        page.insert_text((450, y), f"TL {float(offer_data['grand_total']):.2f}", fontsize=12, fontname=f_bold)
        
        doc.save(filepath)
        doc.close()
        
        return filepath
