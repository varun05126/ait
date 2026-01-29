from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie

from datetime import datetime, timedelta
import io
import json
import os

# -------------------- OPENAI (Chatbot only) --------------------
from openai import OpenAI

OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

if OPENAI_KEY:
    client = OpenAI(api_key=OPENAI_KEY)
else:
    client = None
    print("⚠️ Warning: OPENAI_API_KEY not found. Chatbot will be disabled.")


# -------------------- GEMINI (Trip Planner) --------------------
import google.generativeai as genai

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    print("⚠️ Warning: GEMINI_API_KEY not found. Trip planner will use fallback only.")


def get_itinerary(prompt: str) -> str:
    """
    Call Gemini to generate the raw itinerary text.
    Uses gemini-2.0-flash as you requested.
    """
    if not GEMINI_KEY:
        return ""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        # Gemini Python SDK: response.text holds the combined output
        return getattr(response, "text", "").strip()
    except Exception as e:
        print("Gemini Planner Error:", e)
        return ""


# -------------------- CONTACT FORM / PDF --------------------
from .forms import ContactForm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


# -------------------- CHATBOT API --------------------
@require_http_methods(["POST"])
def chatbot_response(request):
    if client is None:
        return JsonResponse({
            "reply": "Chatbot is unavailable because the API key is missing."
        })

    try:
        data = json.loads(request.body)
        user_msg = data.get("message", "").strip()

        if not user_msg:
            return JsonResponse({"reply": "Please enter a message."})

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_msg},
            ],
        )

        reply = completion.choices[0].message.content.strip()
        return JsonResponse({"reply": reply})

    except Exception as e:
        print("OpenAI Chatbot Error:", e)
        return JsonResponse({"reply": "Something went wrong."})


# -------------------- STATIC PAGES --------------------
def index(request):
    return render(request, "index.html")


def destinations(request):
    return render(request, "destinations.html")


def about(request):
    return render(request, "about.html")


@ensure_csrf_cookie
def chatbot(request):
    return render(request, "chatbot.html")


# -------------------- TRIP PLANNER --------------------
def planner(request):
    plan = None
    destination = start_date = end_date = interests = budget = ""
    estimated_budget = total_days = daily_budget = None

    if request.method == "POST":
        destination = request.POST.get("destination", "").strip()
        start_date = request.POST.get("start_date", "")
        end_date = request.POST.get("end_date", "")
        interests = request.POST.get("interests", "").strip()
        budget = request.POST.get("budget", "").strip()

        # Validate dates (from HTML5 date input -> YYYY-MM-DD)
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect("planner")

        if end < start:
            messages.error(request, "End date must be after start date.")
            return redirect("planner")

        total_days = (end - start).days + 1

        # ----- INTERESTS TEXT -----
        if interests.lower() == "all":
            interests_description = (
                "history, culture, temples, museums, nature, adventure, lakes, "
                "nightlife, food, shopping, hidden gems"
            )
        else:
            interests_description = interests or "popular attractions"

        # ----- GEMINI PROMPT -----
        ai_prompt = f"""
You are a professional Indian travel planner. Generate a REAL, day-wise itinerary for {destination}.

DETAILS:
- City: {destination}
- Start Date: {start.strftime("%d %B %Y")}
- End Date: {end.strftime("%d %B %Y")}
- Total Days: {total_days}
- Traveller Interests: {interests_description}
- Budget Type: {budget} (budget / middle / rich)

STRICT OUTPUT FORMAT (NO bullets, NO extra explanation, NO intro, NO outro):

Day 1 - <DayName>, <Date in dd Month yyyy>
Attraction 1 (short description)
Attraction 2 (short description)
Food: Real restaurant / cafe / hotel with local food
Attraction 3 (short description)
Optional: Shopping place or lake / park

Day 2 - <DayName>, <Date in dd Month yyyy>
Attraction 1
Attraction 2
Food: Some food place
Attraction 3
Shopping / Nightlife place

RULES:
- Use ACTUAL dates between {start.strftime("%d %B %Y")} and {end.strftime("%d %B %Y")}
- At least 4 REAL places per day (famous or good local spots).
- Include at least one REAL food place (restaurant / cafe / hotel) per day.
- Include museums, lakes, shopping streets, etc. when suitable.
- Do NOT add any headings like "Itinerary" or "Summary".
- Do NOT include any Markdown, bullets, or numbering except the "Day X - ..." line.
"""

        # ----- CALL GEMINI -----
        ai_text = get_itinerary(ai_prompt)

        # ----- PARSE GEMINI RESPONSE -----
        # We want plan as: list of days; each day is list of lines (first line is the Day header)
        plan = []
        if ai_text:
            # Split by "Day " to separate blocks
            blocks = ai_text.split("Day ")
            for block in blocks:
                b = block.strip()
                if not b:
                    continue
                lines = [line.strip() for line in b.split("\n") if line.strip()]
                # Put back "Day " prefix to first line
                lines[0] = "Day " + lines[0]
                plan.append(lines)

        # ----- FALLBACK IF GEMINI FAILS -----
        if not plan:
            plan = []
            for i in range(total_days):
                day_date = start + timedelta(days=i)
                title = f"Day {i+1} - {day_date.strftime('%A, %d %B %Y')}"
                plan.append([
                    title,
                    f"Visit popular attractions in {destination or 'the city'}.",
                    "Try a famous local food place.",
                ])

        # ----- BUDGET CALCULATION -----
        budget_rates = {"budget": 3000, "middle": 10000, "rich": 20000}
        daily_budget = budget_rates.get(budget, 5000)
        estimated_budget = daily_budget * total_days

        # ----- PDF EXPORT -----
        if "download" in request.POST:
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4

            # Title
            p.setFont("Helvetica-Bold", 18)
            trip_title = f"Trip Itinerary: {destination or 'Your Trip'}"
            p.drawString(40, height - 40, trip_title)

            y = height - 80

            # Loop through planned days
            for day in plan:
                for line in day:
                    if y < 80:  # new page
                        p.showPage()
                        p.setFont("Helvetica", 11)
                        y = height - 60

                    text = line
                    # Add emojis in PDF text as well (may show as boxes depending on font, but it's fine)
                    if line.startswith("Day"):
                        text = f"📅 {line}"
                        p.setFont("Helvetica-Bold", 14)
                    else:
                        # Simple heuristics for icons
                        lower = line.lower()
                        icon = "📍"
                        if "food" in lower or "restaurant" in lower or "cafe" in lower or "hotel" in lower or "biryani" in lower or "lunch" in lower or "dinner" in lower:
                            icon = "🍽️"
                        elif "museum" in lower or "gallery" in lower:
                            icon = "🖼️"
                        elif "mall" in lower or "market" in lower or "bazaar" in lower or "shopping" in lower:
                            icon = "🛍️"
                        text = f"{icon} {line}"

                        p.setFont("Helvetica", 11)

                    p.drawString(40, y, text)
                    y -= 18

            # Budget summary at the bottom of last page
            y -= 20
            p.setFont("Helvetica-Bold", 12)
            budget_line = f"Estimated Budget: ₹{estimated_budget} (₹{daily_budget}/day × {total_days} days)"
            p.drawString(40, y, budget_line)

            p.save()
            buffer.seek(0)

            return HttpResponse(
                buffer,
                content_type="application/pdf",
                headers={"Content-Disposition": 'attachment; filename="trip_plan.pdf"'},
            )

    # GET request or after POST processing
    return render(request, "planner.html", {
        "plan": plan,
        "destination": destination,
        "start_date": start_date,
        "end_date": end_date,
        "interests": interests,
        "budget": budget,
        "estimated_budget": estimated_budget,
        "total_days": total_days,
        "daily_budget": daily_budget,
    })


# -------------------- CONTACT FORM --------------------
def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            send_mail(
                subject=f"Message from {form.cleaned_data['name']}",
                message=form.cleaned_data['message'],
                from_email=form.cleaned_data['email'],
                recipient_list=["saivardhanuppala7@gmail.com"],
            )
            messages.success(request, "Message sent successfully!")
            return redirect("contact")
    else:
        form = ContactForm()

    return render(request, "contact.html", {"form": form})