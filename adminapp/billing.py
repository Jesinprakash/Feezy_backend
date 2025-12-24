from datetime import timedelta
from django.utils import timezone
from adminapp.models import Member, Bill
from adminapp.serializers import  KOLKATA,calculate_fees
from adminapp.utils import  is_due
from adminapp.config import IS_TESTING

def generate_bills_for_member(member_id):
    today = timezone.now().astimezone(KOLKATA).replace(second=0, microsecond=0)
    member = Member.objects.get(id=member_id)
    created_bills = []

    # ----------------------------
    # FIRST BILL
    # ----------------------------
    if not Bill.objects.filter(member=member, is_recurring=False).exists():
        if member.recurring_date:
            RD = member.recurring_date.astimezone(KOLKATA).replace(second=0, microsecond=0)
            CD = member.created_at.astimezone(KOLKATA).replace(second=0, microsecond=0)

            if RD < CD:
                pass
            elif is_due(RD, today, testing=IS_TESTING):
                subscription = member.subscription
                total = calculate_fees(subscription, include_joining=True)
                bill = Bill.objects.create(
                    member=member,
                    subscription=subscription,
                    total_amount=total,
                    due_amount=total,
                    bill_date=RD,
                    recurring_date=RD,
                    is_recurring=False,
                )
                created_bills.append(bill)

    # ----------------------------
    # RECURRING BILLS
    # ----------------------------
    if member.recurring_date:
        subscription = member.subscription
        duration = getattr(subscription, "duration_days", 30)
        last_bill = Bill.objects.filter(member=member).order_by("-bill_date").first()
        step = timedelta(minutes=duration) if IS_TESTING else timedelta(days=duration)

        if last_bill:
            next_bill_date = last_bill.bill_date + step
        else:
            RD = member.recurring_date.astimezone(KOLKATA).replace(second=0, microsecond=0)
            CD = member.created_at.astimezone(KOLKATA).replace(second=0, microsecond=0)
            next_bill_date = CD + step if RD < CD else RD + step

        next_bill_date = next_bill_date.astimezone(KOLKATA).replace(second=0, microsecond=0)

        while next_bill_date <= today:
            if not Bill.objects.filter(member=member, bill_date=next_bill_date, is_recurring=True).exists():
                total = calculate_fees(subscription, include_joining=False)
                bill = Bill.objects.create(
                    member=member,
                    subscription=subscription,
                    total_amount=total,
                    due_amount=total,
                    bill_date=next_bill_date,
                    recurring_date=next_bill_date,
                    is_recurring=True,
                )
                created_bills.append(bill)
            next_bill_date += step
            next_bill_date = next_bill_date.astimezone(KOLKATA).replace(second=0, microsecond=0)

    return created_bills