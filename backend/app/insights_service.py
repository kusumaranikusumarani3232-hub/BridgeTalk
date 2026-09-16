import re
from typing import List
from app.models import InsightItem

class InsightsService:
    def extract_insights(self, text: str, translation: str = "") -> List[InsightItem]:
        """
        Extracts structured entities and factual insights from conversation text.
        Checks both original text and English translation for matches.
        """
        insights: List[InsightItem] = []
        combined_text = f"{text} {translation}"

        # 1. Date extraction
        dates = re.findall(
            r'\b(today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|kal|aaj|parson|next week)\b',
            combined_text,
            re.IGNORECASE
        )
        if dates:
            formatted_date = dates[0].capitalize()
            # Map Hindi common date terms for display
            if formatted_date.lower() == 'kal':
                formatted_date = "Tomorrow / Yesterday (Kal)"
            elif formatted_date.lower() == 'aaj':
                formatted_date = "Today (Aaj)"
            insights.append(InsightItem(
                category="date",
                label="Date",
                value=formatted_date,
                icon="📅"
            ))

        # 2. Time extraction (e.g., 10:00 AM, 10 o'clock, das baje, 5 pm)
        times = re.findall(
            r'(\b\d{1,2}(?::\d{2})?\s*(?:am|pm|o\'clock)\b|\bdas baje\b|\bpaanch baje\b|\b\d{1,2}\s*baje\b)',
            combined_text,
            re.IGNORECASE
        )
        if times:
            val = times[0]
            if "das baje" in val.lower():
                val = "10:00 AM"
            elif "baje" in val.lower():
                val = val.replace("baje", "o'clock")
            insights.append(InsightItem(
                category="time",
                label="Time",
                value=val,
                icon="🕙"
            ))

        # 3. Location extraction (office, airport, hotel, restaurant, home, station, etc.)
        locations = re.findall(
            r'\b(office|home|airport|station|restaurant|hotel|hospital|cafe|dft|delhi|mumbai|london|bangalore)\b',
            combined_text,
            re.IGNORECASE
        )
        if locations:
            insights.append(InsightItem(
                category="location",
                label="Location",
                value=locations[0].capitalize(),
                icon="📍"
            ))

        # 4. Currency / Amounts
        amounts = re.findall(
            r'(\$\d+(?:\.\d{2})?|\b\d+\s*(?:dollars|rupees|rs|inr|usd|euros)\b)',
            combined_text,
            re.IGNORECASE
        )
        if amounts:
            insights.append(InsightItem(
                category="amount",
                label="Amount",
                value=amounts[0],
                icon="💵"
            ))

        # 5. Topic / Request type (meeting, meet, call, dinner, lunch, flight, payment)
        topics = re.findall(
            r'\b(meeting|meet|call|dinner|lunch|flight|schedule|interview|presentation|payment|discussion)\b',
            combined_text,
            re.IGNORECASE
        )
        if topics:
            val = topics[0].capitalize()
            if val.lower() == 'meet':
                val = "Meeting"
            insights.append(InsightItem(
                category="topic",
                label="Topic",
                value=val,
                icon="📌"
            ))

        return insights

insights_service = InsightsService()
