from django import forms
# from django.contrib.auth.models import User
from .models import Flight, User


class PassengerInfoForm(forms.Form):
    leave_city = forms.CharField(label='leave_city', max_length=100)
    arrive_city = forms.CharField(label='arrive_city', max_length=100)
    leave_date = forms.DateField(label='leave_date')


class MemberInfo(forms.Form):
    member_id = forms.IntegerField(label='member_id',max_value=10000)
    member_name = forms.CharField(label='member_name', max_length=100)


# 自定义Flight对象的输入信息
class FlightForm(forms.ModelForm):
    class Meta:
        model = Flight
        exclude = ['user', 'book_sum', 'income']  # user信息不能从后台输入


# 用户需要输入的字段
class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'pid']
