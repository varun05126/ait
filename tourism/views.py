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

# ==================== GROQ (AI ENGINE) ====================
from groq import Groq

GROQ_KEY = os.environ.get("GROQ_API_KEY")

if GROQ_KEY:
    groq_client = Groq(api_key=GROQ_KEY)
else:
    groq_client = None
    print("⚠️ GROQ_API_KEY not found. AI features disabled.")


def groq_generate(prompt, system="You are a helpful assistant."):
    if not groq_client:
        return ""

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
        )
        return completion.choices[0].message.content.strip()

    except Exception as e:
        print("Groq Error:", e)
        return ""


# ==================== PDF & CONTACT ====================
from .forms import ContactForm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


# ==================== CHATBOT API ====================
@require_http_methods(["POST"])
def chatbot_response(request):
    if not groq_client:
        return JsonResponse({"reply": "Chatbot is currently unavailable."})

    try:
        data = json.loads(request.body)
        user_msg = data.get("message", "").strip()

        if not user_msg:
            return JsonResponse({"reply": "Please type a message."})

        reply = groq_generate(
            user_msg,
            system="You are a smart, friendly, luxury AI travel assistant. Give helpful, clear travel advice."
        )

        return JsonResponse({"reply": reply or "I couldn't generate a response."})

    except Exception as e:
        print("Chatbot Error:", e)
        return JsonResponse({"reply": "Something went wrong."})


# ==================== STATIC PAGES ====================
def index(request):
    return render(request, "base.html")


def destinations(request):
    return render(request, "destinations.html")


def about(request):
    return render(request, "about.html")


@ensure_csrf_cookie
def chatbot(request):
    return render(request, "chatbot.html")


# ==================== TRIP PLANNER ====================
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

        # ---- DATE VALIDATION ----
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

        # ---- INTERESTS ----
        interests_description = interests or "popular attractions, food, culture, nature"

        # ---- PROMPT ----
        ai_prompt = f"""
You are a professional Indian travel planner.

Create a REAL, day-wise itinerary for {destination}.

DETAILS:
City: {destination}
Start: {start.strftime("%d %B %Y")}
End: {end.strftime("%d %B %Y")}
Days: {total_days}
Interests: {interests_description}
Budget: {budget}

FORMAT STRICTLY LIKE THIS:

Day 1 - Monday, 12 March 2026
Place 1 (short description)
Place 2
Food: Real restaurant or cafe
Place 3
Optional evening place

RULES:
- Use REAL locations
- At least 4 places per day
- Include food daily
- NO markdown, bullets, headings, or explanations
"""

        ai_text = groq_generate(
            ai_prompt,
            system="You are a professional luxury travel planner who designs premium, realistic travel itineraries."
        )

        # ---- PARSE PLAN ----
        plan = []
        if ai_text:
            blocks = ai_text.split("Day ")
            for block in blocks:
                b = block.strip()
                if not b:
                    continue
                lines = [line.strip() for line in b.split("\n") if line.strip()]
                lines[0] = "Day " + lines[0]
                plan.append(lines)

        # ---- FALLBACK ----
        if not plan:
            plan = []
            for i in range(total_days):
                date = start + timedelta(days=i)
                plan.append([
                    f"Day {i+1} - {date.strftime('%A, %d %B %Y')}",
                    f"Explore famous attractions in {destination}.",
                    "Try popular local food spots.",
                    "Visit markets, parks, or heritage places."
                ])

        # ---- BUDGET ----
        budget_rates = {"budget": 3000, "middle": 10000, "rich": 20000}
        daily_budget = budget_rates.get(budget, 5000)
        estimated_budget = daily_budget * total_days

        # ---- PDF EXPORT ----
        if "download" in request.POST:
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4

            p.setFont("Helvetica-Bold", 18)
            p.drawString(40, height - 40, f"Trip Itinerary – {destination}")
            y = height - 80

            for day in plan:
                for line in day:
                    if y < 80:
                        p.showPage()
                        y = height - 60

                    if line.startswith("Day"):
                        p.setFont("Helvetica-Bold", 14)
                        p.drawString(40, y, "📅 " + line)
                        y -= 22
                    else:
                        p.setFont("Helvetica", 11)
                        p.drawString(40, y, "📍 " + line)
                        y -= 16

            y -= 20
            p.setFont("Helvetica-Bold", 12)
            p.drawString(40, y, f"Estimated Budget: ₹{estimated_budget}")

            p.save()
            buffer.seek(0)

            return HttpResponse(
                buffer,
                content_type="application/pdf",
                headers={"Content-Disposition": 'attachment; filename="AIT_Trip_Plan.pdf"'},
            )

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


# ==================== CONTACT ====================
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
