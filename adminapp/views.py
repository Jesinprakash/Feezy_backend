from django.shortcuts import render
from dateutil.relativedelta import relativedelta

from adminapp.serializers import CategorySerializer,LoginSerializer,ClientCreateSerializer,PasswordUpdateSerializer,ForgotPasswordSerializer,BatchSerializer,SubscriptionSerializer,MemberSerializer,PaymentSerializer,calculate_fees,BillSerializer,BillFeeSerializer,AttendanceSerializer
import pytz

from rest_framework import generics
from decimal import Decimal

from adminapp.models import Category,Client,Batch,Subscription,Member,Payment,Bill,Attendance
from rest_framework import authentication,permissions,status

from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from datetime import date, timedelta
from django.utils import timezone
from adminapp.config import IS_TESTING


class GetTokenApiView(APIView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            username = serializer.validated_data.get("username")
            password = serializer.validated_data.get("password")

            # Authenticate user (checks hashed password)
            user = authenticate(request, username=username, password=password)

            if user is not None:
                # ✅ Check if subscription expired
                if user.subscription_end and user.subscription_end < timezone.now():
                    user.is_active = False
                    user.save()
                    return Response(
                        {"message": "Your subscription has expired. Please contact admin to renew."},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # ✅ Block login for inactive users
                if not user.is_active:
                    return Response(
                        {"message": "Account is inactive. Please contact admin."},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # ✅ If active and not expired → create or get token
                token, created = Token.objects.get_or_create(user=user)
                return Response(
                    {
                        "token": token.key,
                        "username": user.username,
                        "message": "Login successful",
                    },
                    status=status.HTTP_200_OK
                )

            else:
                return Response(
                    {"message": "Invalid username or password"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        # If serializer invalid
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryCreateApiView(generics.ListCreateAPIView):

    serializer_class=CategorySerializer

    queryset=Category.objects.all()

    permission_classes=[permissions.IsAdminUser]

    authentication_classes=[authentication.TokenAuthentication]
    

class ClientRegisterApiView(generics.ListCreateAPIView):
    serializer_class = ClientCreateSerializer
    queryset = Client.objects.all()
    permission_classes = [permissions.IsAdminUser] 
    authentication_classes=[authentication.TokenAuthentication] 
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)  

        client = serializer.save()

        return Response(
            {
                "message": "Client registered successfully",
                "client": serializer.data,
                "subscription_details": {
                    "amount": f"{client.subscription_amount}",
                    "valid_till": client.subscription_end,
                    "status": "Active" if client.is_active else "Inactive",
                }
            },
            status=status.HTTP_201_CREATED
        )

    


class LogoutApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Delete the user's token (logs them out)
        request.user.auth_token.delete()
        return Response(
            {"message": "Logged out successfully"},
            status=status.HTTP_200_OK
        )


class PasswordUpdateApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = PasswordUpdateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ClientUpdateRetrieveDeleteView(generics.RetrieveUpdateDestroyAPIView):

    permissions_classess = [permissions.IsAdminUser]
    authentication_classes=[authentication.TokenAuthentication]

    queryset=Client.objects.all()

    serializer_class=ClientCreateSerializer

    authentication_classes=[authentication.TokenAuthentication]

    permission_classes=[permissions.IsAdminUser]







class ClientRenewApiView(APIView):
    permission_classes = [permissions.IsAdminUser]  
    authentication_classes=[authentication.TokenAuthentication]

    def post(self, request, pk, *args, **kwargs):
        client = get_object_or_404(Client, pk=pk)

        # Ensure subscription_end exists
        if not client.subscription_end:
            return Response(
                {"error": "Client does not have an active subscription."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if current date is within 5 days before the subscription_end
        today = timezone.now()
        days_left = (client.subscription_end - today).days

        if days_left > 5:
            return Response(
                {"error": f"Subscription can only be renewed within the last 5 days. ({days_left} days left)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate previous subscription duration
        old_duration = (
            (client.subscription_end - client.subscription_start).days
            if client.subscription_start and client.subscription_end
            else 365
        )

        # Renew with same details
        client.renew_subscription(
            duration_days=old_duration,
            amount=client.subscription_amount,
            currency=client.subscription_currency
        )

        return Response({
            "message": f"{client.business_name or client.username}'s subscription renewed successfully!",
            "subscription_start": timezone.localtime(client.subscription_start).strftime("%d-%b-%Y %I:%M %p"),
            "subscription_end": timezone.localtime(client.subscription_end).strftime("%d-%b-%Y %I:%M %p"),
            "subscription_amount": client.subscription_amount,
            "subscription_currency": client.subscription_currency,
        }, status=status.HTTP_200_OK)



class ForgotPasswordApiView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "New password sent to your email."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class BatchCreateListApiView(generics.ListCreateAPIView):

    serializer_class = BatchSerializer

    authentication_classes = [authentication.TokenAuthentication]

    # authentication_classes=[authentication.BasicAuthentication]

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):

        return Batch.objects.filter(client=self.request.user)

    def perform_create(self, serializer):

        serializer.save(client=self.request.user)


class BatchUpdateRetriveDeleteApiView(generics.RetrieveUpdateDestroyAPIView):

    serializer_class=BatchSerializer

    authentication_classes=[authentication.TokenAuthentication]

    # authentication_classes=[authentication.BasicAuthentication]


    permission_classes=[permissions.IsAuthenticated]

    def get_queryset(self):
        
        return Batch.objects.filter(client=self.request.user)




class SubscriptionListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes=[authentication.TokenAuthentication]

    # authentication_classes=[authentication.BasicAuthentication]



    def get_queryset(self):
        return Subscription.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)


class SubscriptionRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [authentication.TokenAuthentication]

    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Subscription.objects.filter(client=self.request.user)
    
    
class MemberListCreateApiView(generics.ListCreateAPIView):
    permissions_classess = [permissions.IsAuthenticated]
    authentication_classes=[authentication.TokenAuthentication]
    # authentication_classes=[authentication.BasicAuthentication]
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    def get_queryset(self):
        # request.user IS Client
        return Member.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        # auto-assign logged-in client
        serializer.save(client=self.request.user)

class MemberRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    permissions_classess = [permissions.IsAuthenticated]
    authentication_classes=[authentication.TokenAuthentication]
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    def get_queryset(self):
        return Member.objects.filter(client=self.request.user)
 
 
# bills of a particular member    
class MemberBillsView(generics.ListAPIView):
    permissions_classess = [permissions.IsAuthenticated]
    authentication_classes=[authentication.TokenAuthentication]
    serializer_class = BillSerializer

    def get_queryset(self):
        member_id = self.kwargs['member_id']
        return Bill.objects.filter(member_id=member_id).order_by('bill_date')

# fees of  a particular bill
class BillFeesView(generics.RetrieveAPIView):
    permissions_classess = [permissions.IsAuthenticated]
    authentication_classes=[authentication.TokenAuthentication]
    queryset = Bill.objects.all()
    serializer_class = BillFeeSerializer
 
    
class PaymentListCreateView(generics.ListCreateAPIView):
    permissions_classess = [permissions.IsAuthenticated]
    authentication_classes=[authentication.TokenAuthentication]
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    def get_queryset(self):
        # request.user IS Client
        return Payment.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        # auto-assign logged-in client
        serializer.save(client=self.request.user)

class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permissions_classess = [permissions.IsAuthenticated]
    authentication_classes=[authentication.TokenAuthentication]
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer



class AttendanceListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # ✅ Only attendance of logged-in client
        return Attendance.objects.filter(
            client=self.request.user
        )

    def perform_create(self, serializer):
        # ✅ Client auto assigned
        serializer.save(
            client=self.request.user,
            date=serializer.validated_data.get(
                'date', timezone.now().date()
            )
        )