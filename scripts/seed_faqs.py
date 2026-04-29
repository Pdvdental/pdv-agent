"""
Seeds initial FAQs into Supabase.
Usage: python scripts/seed_faqs.py
Requires .env with SUPABASE_URL and SUPABASE_SERVICE_KEY.
"""
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
import os

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

FAQS = [
    {
        "category": "servicios",
        "question": "¿Qué servicios ofrecéis?",
        "answer": (
            "En PDV ofrecemos: implantes dentales, ortodoncia y alineadores, estética dental, "
            "endodoncia, prótesis fija y removible, odontología restauradora, e higiene y prevención. "
            "Para más información o presupuesto, pide cita y te hacemos una valoración gratuita."
        ),
    },
    {
        "category": "precios",
        "question": "¿Cuánto cuesta una limpieza dental?",
        "answer": (
            "La limpieza dental (higiene bucodental) tiene un precio orientativo de entre 60 y 90 €, "
            "dependiendo del estado de la boca. Incluye eliminación de sarro, pulido y revisión. "
            "El precio exacto te lo confirmamos en la visita."
        ),
    },
    {
        "category": "precios",
        "question": "¿Cuánto cuesta una revisión o primera visita?",
        "answer": (
            "La primera visita incluye exploración completa y radiografías básicas. "
            "Precio orientativo: 30-50 €. En muchos casos la revisión es gratuita si luego realizas el tratamiento con nosotros. "
            "Llámanos para confirmarlo: 93 729 4880."
        ),
    },
    {
        "category": "precios",
        "question": "¿Cuánto cuestan los implantes?",
        "answer": (
            "El precio de un implante depende del caso: número de implantes, necesidad de injerto óseo, tipo de prótesis... "
            "No podemos dar precio cerrado sin evaluación. Te ofrecemos una valoración presencial gratuita sin compromiso. "
            "Pide cita y te explicamos todo con detalle."
        ),
    },
    {
        "category": "precios",
        "question": "¿Cuánto cuesta la ortodoncia o los alineadores?",
        "answer": (
            "La ortodoncia (brackets o alineadores tipo Invisalign/similares) varía mucho según el caso. "
            "Rango orientativo: 1.500 - 4.500 €. Necesitamos verte para darte un presupuesto real. "
            "La primera valoración es gratuita."
        ),
    },
    {
        "category": "horarios",
        "question": "¿Cuál es vuestro horario?",
        "answer": (
            "Atendemos de lunes a jueves. Para saber el horario exacto de cada día o disponibilidad, "
            "dime qué día prefieres y busco huecos disponibles en el calendario."
        ),
    },
    {
        "category": "ubicacion",
        "question": "¿Dónde estáis? ¿Cómo llego?",
        "answer": (
            "Estamos en Carrer Tibidabo 78B-1, Barberà del Vallès (Barcelona). "
            "Hay parking gratuito en la zona. Cerca de la estación de Barberà del Vallès (R4 y R8). "
            "Google Maps: busca 'PDV Policlínica Dental del Vallès'."
        ),
    },
    {
        "category": "ubicacion",
        "question": "¿Hay parking cerca?",
        "answer": (
            "Sí, hay parking gratuito en la calle junto a la clínica. "
            "Si tienes algún problema para aparcar, llámanos al 93 729 4880 y te indicamos la mejor opción."
        ),
    },
    {
        "category": "primera_visita",
        "question": "¿Qué pasa en la primera visita?",
        "answer": (
            "En la primera visita hacemos una exploración completa de tu boca: revisión de dientes, encías y mordida. "
            "Si es necesario, tomamos radiografías. Al final te explicamos el diagnóstico y las opciones de tratamiento, "
            "sin presión ni compromiso."
        ),
    },
    {
        "category": "pago",
        "question": "¿Qué formas de pago aceptáis?",
        "answer": (
            "Aceptamos efectivo, tarjeta (débito y crédito) y transferencia. "
            "Para tratamientos de mayor importe ofrecemos financiación sin intereses. "
            "Pregúntanos en clínica para más detalles."
        ),
    },
    {
        "category": "urgencias",
        "question": "Tengo dolor de muelas, ¿podéis atenderme hoy?",
        "answer": (
            "Para urgencias del mismo día llama directamente al 93 729 4880. "
            "Intentamos reservar huecos para urgencias. Si hay dolor agudo, hinchazón o trauma dental, "
            "llama ahora y te atendemos lo antes posible."
        ),
    },
    {
        "category": "contacto",
        "question": "¿Cuál es el teléfono de la clínica?",
        "answer": (
            "Puedes llamarnos al 93 729 4880 o al 93 729 2869. "
            "También al móvil: 677 523 665. "
            "O escríbenos a pdvdental@hotmail.com."
        ),
    },
]

result = db.table("faqs").insert(FAQS).execute()
print(f"✅ {len(result.data)} FAQs insertadas correctamente.")