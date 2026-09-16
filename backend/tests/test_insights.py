from app.insights_service import insights_service

def test_extract_date_time_location():
    text = "Can you meet me tomorrow at 10 AM near the office?"
    translation = "क्या आप कल सुबह 10 बजे ऑफिस के पास मिल सकते हैं?"
    
    insights = insights_service.extract_insights(text, translation)
    
    categories = [i.category for i in insights]
    assert "date" in categories
    assert "time" in categories
    assert "location" in categories
    assert "topic" in categories

def test_extract_hindi_date():
    text = "Kal meeting ke liye aana"
    insights = insights_service.extract_insights(text)
    categories = [i.category for i in insights]
    assert "date" in categories
