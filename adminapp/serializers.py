import random,pytz
import string
import requests
from datetime import date, timedelta,datetime
from django.utils import timezone

from rest_framework import serializers
from adminapp.models import Client,Category,Batch,Subscription,Member,Payment,Bill
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from dateutil.relativedelta import relativedelta
from decimal import Decimal


Client = get_user_model()


class ClientCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(read_only=True)
    country_code = serializers.CharField(write_only=True, required=False)  # ✅ for currency API

    class Meta:
        model = Client
        fields = [
            'username',
            'email',
            'password',
            'business_name',
            'contact_number',
            'address',
            'payment_method',
            'country_code',            # used for currency lookup
            'subscription_amount',
            'subscription_currency',   # ✅ updated to match your model
            'subscription_start',
            'subscription_end',
            'is_active',
            'category',
            'currency_emoji',          # ✅ allow frontend to send emoji
        ]
        read_only_fields = [
            'password',
            'subscription_amount',
            'subscription_currency',
            'subscription_start',
            'subscription_end',
            'is_active',
        ]

    def create(self, validated_data):
        # 🔹 Extract and remove country code (keep currency_emoji)
        country_code = validated_data.pop('country_code', 'IN')

        # 🔹 Generate random password (10 characters)
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

        # 🔹 Create client instance with provided data (includes emoji)
        client = Client(**validated_data)
        client.set_password(password)

        # --- Subscription setup ---
        # client.subscription_start = date.today()
        client.subscription_start = timezone.now()
        client.subscription_end = client.subscription_start + timedelta(days=365)
        client.subscription_amount = 5000.00  # base price
        client.subscription_currency = "INR"  # default

        # --- Fetch currency from API (based on country_code) ---
        try:
            api_url = f"https://restcountries.com/v3.1/alpha/{country_code}"
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()[0]
                currency_code = list(data["currencies"].keys())[0]
                client.subscription_currency = currency_code
            else:
                client.subscription_currency = "INR"
        except Exception as e:
            print("Currency fetch failed:", e)
            client.subscription_currency = "INR"

        # 🔹 Save the client (includes manually entered emoji)
        client.save()

        # Attach generated password for API response
        client.generated_password = password

        # --- Send email with credentials ---
        subject = "Your Account Credentials"
        message = (
            f"Hello {client.username},\n\n"
            f"Your account has been created successfully.\n\n"
            f"Here are your login details:\n"
            f"Username: {client.username}\n"
            f"Password: {password}\n\n"
            f"Subscription: 1 Year\n"
            f"Amount: {client.subscription_amount} {client.subscription_currency}\n"
            f"Valid Till: {client.subscription_end}\n\n"
            f"Please change your password after your first login.\n\n"
            f"Regards,\nAdmin Team"
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client.email], fail_silently=False)

        return client

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if hasattr(instance, 'generated_password'):
            data['generated_password'] = instance.generated_password
        return data
        
# -------- Login Serializer --------
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True) 


# -------- Category Serializer --------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ["id"]

class PasswordUpdateSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context['request'].user

        # Check old password
        if not user.check_password(data['old_password']):
            raise serializers.ValidationError({"old_password": "Incorrect old password"})

        # Check if new passwords match
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})

        # Optional: Add password strength checks
        if len(data['new_password']) < 6:
            raise serializers.ValidationError({"new_password": "Password must be at least 6 characters long"})

        return data

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not Client.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email.")
        return value

    def save(self):
        email = self.validated_data['email']
        user = Client.objects.get(email=email)

        # --- Generate a random 10-character password ---
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        
        # --- Set the new password (hashed automatically) ---
        user.set_password(new_password)
        user.save()

        # --- Send email to the user ---
        subject = "Your New Password"
        message = f"Hello {user.username},\n\nYour new password is: {new_password}\n\nPlease log in and change it immediately."
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [email]
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
    
class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = ['client','name','start_time','end_time','days']




KOLKATA = pytz.timezone("Asia/Kolkata")


def calculate_fees(subscription, include_joining=False):
    total = Decimal("0.00")
    if include_joining:
        total += Decimal(subscription.admission_fee or 0)
        for fee in subscription.custom_fees:
            if not fee.get("recurring", False):
                total += Decimal(fee.get("value", 0))
    for fee in subscription.custom_fees:
        if fee.get("recurring", False):
            total += Decimal(fee.get("value", 0))
    return total




class MemberSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format='%d-%m-%Y %H:%M',read_only=True)
    recurring_date = serializers.DateTimeField(
        input_formats=['%d-%m-%Y %H:%M'],  # how the serializer expects input
        format='%d-%m-%Y %H:%M',           # how the serializer outputs the date
        
    )

    
    class Meta:
        model = Member
        fields = "__all__"
        
        
  

    def create(self, validated_data):

        member = Member.objects.create(**validated_data)

        if not member.recurring_date:
            return member

        # Convert to DATE ONLY
        RD = member.recurring_date.astimezone(KOLKATA)
        CD = member.created_at.astimezone(KOLKATA)
        
                # Normalize to ignore seconds and microseconds
        RD = RD.replace(second=0, microsecond=0)
        CD = CD.replace(second=0, microsecond=0)

        print("DEBUG-RD-date:", RD)
        print("DEBUG-CD-date:", CD)

        subscription = member.subscription
        duration_days = getattr(subscription, "duration_days", 30)

        # ---------------------------------------------------
        # NO BILL RULES
        # ---------------------------------------------------

        # 1️⃣ RECURRING DATE IN THE FUTURE → NO BILL
        if RD > CD:
            return member  # DO NOT CREATE FIRST BILL

        # 2️⃣ RECURRING DATE IN THE PAST → NO BILL
        if RD < CD:
            return member  # DO NOT CREATE FIRST BILL

        # 3️⃣ RECURRING DATE == CREATED DATE → ONLY CASE TO CREATE BILL
        bill_date = member.recurring_date.astimezone(KOLKATA)
        include_joining = True

        total = calculate_fees(subscription, include_joining=True)

        Bill.objects.create(
            member=member,
            subscription=subscription,
            total_amount=total,
            due_amount=total,
            bill_date=bill_date,
            recurring_date=member.recurring_date,
            is_recurring=False,  # first bill
        )

        return member
    
    
class BillFeeSerializer(serializers.ModelSerializer):
    fees_status = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = ['id', 'bill_date', 'total_amount', 'fees_status']

    def get_fees_status(self, bill):
        subscription = bill.subscription
        member = bill.member
        status = []

        # Admission Fee → only in first bill
        if not bill.is_recurring:
            admission_paid = Bill.objects.filter(
                member=member,
                subscription=subscription,
                is_recurring=False,
                paid_amount__gte=subscription.admission_fee
            ).exists()
            if subscription.admission_fee > 0:
                status.append({
                    "name": "Admission Fee",
                    "value": subscription.admission_fee,
                    "is_paid": admission_paid
                })

        # Custom fees
        for fee in subscription.custom_fees:
            fee_name = fee.get("field")
            fee_value = Decimal(fee.get("value", 0))
            recurring = fee.get("recurring", False)

            # Show recurring always, non-recurring only in first bill
            if recurring or (not recurring and not bill.is_recurring):
                paid = Bill.objects.filter(
                    member=member,
                    subscription=subscription,
                    is_recurring=recurring,
                    paid_amount__gte=fee_value
                ).exists()
                status.append({
                    "name": fee_name,
                    "value": fee_value,
                    "is_paid": paid
                })
        return status



class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta: 
        model = Subscription
        fields = '__all__'


class BillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bill
        # optionally, you can exclude fields or set read_only_fields
        fields = '__all__'
        read_only_fields = ('paid_amount', 'due_amount', 'bill_date')

    # Optionally, if you want to show member details nested:
    # member = serializers.StringRelatedField(read_only=True)
    # subscription = SubscriptionSerializer(read_only=True)


class PaymentSerializer(serializers.ModelSerializer):
    payment_date = serializers.DateTimeField(format='%d-%m-%Y %H:%M',read_only=True)
   
    class Meta:
        model = Payment
        fields = ['id','bill','amount','payment_method','payment_date']
        
    def validate(self, attrs):
        bill = attrs.get('bill')
        amount = attrs.get('amount')
 
        if bill.due_amount < amount:
            raise serializers.ValidationError("Payment cannot exceed bill due amount")
        return attrs

    def create(self, validated_data):
        payment = super().create(validated_data)
        # The Payment.save() logic will auto‑update Bill's paid / due amounts
        return payment
    
    


from rest_framework import serializers
from django.utils import timezone
from .models import Attendance

class AttendanceSerializer(serializers.ModelSerializer):

    class Meta:
        model = Attendance
        fields = [
            'id',
            'member',
            'batch',
            'date',
            'present',
            'remarks'
        ]

        read_only_fields=["id","batch"]

    def validate_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                "Attendance date cannot be in the future"
            )
        return value

    def validate(self, data):
        request = self.context['request']
        client = request.user

        member = data.get('member')
        batch = data.get('batch')
        date = data.get('date')

        # ✅ Member must belong to logged-in client
        if member.client != client:
            raise serializers.ValidationError(
                "You cannot mark attendance for this member"
            )

        # ✅ If batch is provided → validate
        if batch:
            if batch.client != client:
                raise serializers.ValidationError(
                    "You cannot use this batch"
                )

            if member.batch_group != batch:
                raise serializers.ValidationError(
                    "Member does not belong to this batch"
                )

        # ✅ Prevent duplicate attendance
        if self.instance is None:
            if Attendance.objects.filter(
                member=member,
                batch=batch,
                date=date
            ).exists():
                raise serializers.ValidationError(
                    "Attendance already marked for this date"
                )

        return data

    


