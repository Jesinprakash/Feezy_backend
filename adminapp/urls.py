from django.urls import path

from adminapp import views

urlpatterns = [

    path('category/',views.CategoryCreateApiView.as_view()),

    path('user/',views.ClientRegisterApiView.as_view()),

    path('token/',views.GetTokenApiView.as_view()),

    path('update-password/',views.PasswordUpdateApiView.as_view()),

    path('client/<int:pk>/',views.ClientUpdateRetrieveDeleteView.as_view()),

    path('clients/<int:pk>/renew/',views.ClientRenewApiView.as_view()),

    path('forgot-password/',views.ForgotPasswordApiView.as_view()),

    path('logout/',views.LogoutApiView.as_view()),

    path('batch-create/',views.BatchCreateListApiView.as_view()),

    path('batch/<int:pk>/',views.BatchUpdateRetriveDeleteApiView.as_view()),
    
    path('subscriptions/', views.SubscriptionListCreateAPIView.as_view(), name='subscription-list-create'),

    path('subscriptions/<int:pk>/', views.SubscriptionRetrieveUpdateDestroyAPIView.as_view(), name='subscription-detail'),

    path('members/', views.MemberListCreateApiView.as_view(), name='member-list-create'),
    
    path('members/<int:pk>/', views.MemberRetrieveUpdateDestroyAPIView.as_view(), name='member-detail'),
    
    path('payments/', views.PaymentListCreateView.as_view(), name='payment-list-create'),
    
    path('payments/<int:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),
            
    # Get bills for selected member
    path('members/<int:member_id>/bills/', views.MemberBillsView.as_view(), name='member-bills'),

    # Get fees of a particular bill
    path('bills/<int:pk>/fees/', views.BillFeesView.as_view(), name='bill-fees'),

    path('attandence/',views.AttendanceListCreateAPIView.as_view()),


    
    

]