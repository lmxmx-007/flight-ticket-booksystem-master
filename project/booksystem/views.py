from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from .forms import PassengerInfoForm, UserForm, FlightForm, MemberInfo
from .models import Flight, User, Group
from .classes import IncomeMetric, Order
# from django.contrib.auth.models import Permission, User
import datetime, pytz
from operator import attrgetter

ADMIN_ID = 1

global_passenger_lcity = None
global_passenger_acity = None
global_passenger_ldate = None
global_usable_flights_by_ltime = None
global_usable_flights_by_atime = None
global_usable_flights_by_price = None


# 管理员后台财务管理
# 统计航空公司每周、每月，每年营业收入情况。
def admin_finance(request):
    all_flights = Flight.objects.all()
    all_flights = sorted(all_flights, key=attrgetter('leave_time'))  # 将所有航班按照起飞时间排序

    # 将航班每天的输入打上不同的时间标签 [周，月，日]
    week_day_incomes = []
    month_day_incomes = []
    year_day_incomes = []

    # 用set存储所有的 周，月，年
    week_set = set()
    month_set = set()
    year_set = set()
    for flight in all_flights:
        if flight.income > 0:  # 只统计有收入的航班
            # 打上周标签
            this_week = flight.leave_time.strftime('%W')  # datetime获取周
            week_day_incomes.append((this_week, flight.income))  # 添加元组(week, income)
            week_set.add(this_week)
            # 打上月标签
            this_month = flight.leave_time.strftime('%m')  # datetime获取月
            month_day_incomes.append((this_month, flight.income))  # 添加元组(month, income)
            month_set.add(this_month)
            # 打上年标签
            this_year = flight.leave_time.strftime('%Y')  # datetime获取年
            year_day_incomes.append((this_year, flight.income))  # 添加元组(year, income)
            year_set.add(this_year)

    # 存储每周收入
    # 将每周的收入用 IncomeMetric 类型存储在 week_incomes List中
    week_incomes = []
    for week in week_set:
        income = sum(x[1] for x in week_day_incomes if x[0] == week)  # 同周次的income求和
        flight_sum = sum(1 for x in week_day_incomes if x[0] == week)  # 同周次的航班总数目
        week_income = IncomeMetric(week, flight_sum, income)  # 将数据存储到IncomeMetric类中，方便jinja语法
        week_incomes.append(week_income)
    week_incomes = sorted(week_incomes, key=attrgetter('metric'))  # 将List类型的 week_incomes 按周次升序排列

    # 存储每月收入
    # 将每月的收入用 IncomeMetric 类型存储在 month_incomes List中
    month_incomes = []
    for month in month_set:
        income = sum(x[1] for x in month_day_incomes if x[0] == month)
        flight_sum = sum(1 for x in month_day_incomes if x[0] == month)
        month_income = IncomeMetric(month, flight_sum, income)
        month_incomes.append(month_income)
    month_incomes = sorted(month_incomes, key=attrgetter('metric'))  # 将List类型的 month_incomes 按月份升序排列

    # 存储每年收入
    # 将每年的收入用 IncomeMetric 类型存储在 year_incomes List中
    year_incomes = []
    for year in year_set:
        income = sum(x[1] for x in year_day_incomes if x[0] == year)
        flight_sum = sum(1 for x in year_day_incomes if x[0] == year)
        year_income = IncomeMetric(year, flight_sum, income)
        year_incomes.append(year_income)
    year_incomes = sorted(year_incomes, key=attrgetter('metric'))  # 将List类型的 year_incomes 按年份升序排列

    # 存储order信息
    passengers = User.objects.exclude(pk=1)  # 去掉管理员
    order_set = set()
    for p in passengers:
        flights = Flight.objects.filter(user=p)
        for f in flights:
            route = f.leave_city + ' → ' + f.arrive_city
            order = Order(p.username, f.name, route, f.leave_time, f.price)
            order_set.add(order)

    # 信息传给前端
    context = {
        'week_incomes': week_incomes,
        'month_incomes': month_incomes,
        'year_incomes': year_incomes,
        'order_set': order_set
    }
    return context


# 管理员添加航班
def admin(request):
    if request.method == 'POST':
        form = FlightForm(request.POST)  # 绑定数据至表单
        if form.is_valid():
            flight = form.save(commit=False)
            flight.save()
            return render(request, 'booksystem/admin.html')
        else:
            print("无效！")
            return render(request, 'booksystem/admin.html')

    else:
        return render(request, 'booksystem/admin.html')


# 显示用户订单信息
# 航班信息，退票管理
def user_info(request):
    if request.user.is_authenticated:
        # 如果用户是管理员，render公司航班收入统计信息页面 admin_finance
        if request.user.id == ADMIN_ID:
            context = admin_finance(request)  # 获取要传入前端的数据
            # return render(request, 'booksystem/admin_finance.html', context)
        # 如果用户是普通用户，render用户的机票信息 user_info
        else:
            booked_flights = Flight.objects.filter(user=request.user)  # 从 booksystem_flight_user 表过滤出该用户订的航班
            context = {
                'booked_flights': booked_flights,
                'username': request.user.username,  # 导航栏信息更新
            }
            return render(request, 'booksystem/user_info.html', context)
    return render(request, 'booksystem/login.html')  # 用户如果没登录，render登录页面


# 主页
# 欢迎页面性质的订票页面
def index(request):
    return render(request, 'booksystem/result.html')


# 免除csrf
@csrf_exempt
def book_ticket(request, flight_id):
    if not request.user.is_authenticated:  # 如果没登录就render登录页面
        return render(request, 'booksystem/login.html')
    else:
        flight = Flight.objects.get(pk=flight_id)
        # 查看乘客已经订购的flights
        booked_flights = Flight.objects.filter(user=request.user)  # 返回 QuerySet

        if flight in booked_flights:
            return render(request, 'booksystem/book_conflict.html')

        # book_flight.html 点确认之后，request为 POST 方法，虽然没有传递什么值，但是传递了 POST 信号
        # 确认订票，flight数据库改变

        # 验证一下，同样的机票只能订一次
        if request.method == 'POST':
            if flight.capacity > 0:
                flight.book_sum += 1
                flight.capacity -= 1
                flight.income += flight.price
                flight.user.add(request.user)
                flight.save()  # 一定要记着save
        # 传递更改之后的票务信息
        context = {
            'flight': flight,
            'username': request.user.username
        }
        return render(request, 'booksystem/book_flight.html', context)


# 退票
def refund_ticket(request, flight_id):
    flight = Flight.objects.get(pk=flight_id)
    flight.book_sum -= 1
    flight.capacity += 1
    flight.income -= flight.price
    flight.user.remove(request.user)
    flight.save()
    return HttpResponseRedirect('/booksystem/user_info')


def group_refund(request, flight_id):
    group_obj = Group.objects.get(name=request.user.username)
    group_user = group_obj.users.all()
    flight = Flight.objects.get(pk=flight_id)
    group_obj.flight.remove(flight)
    for user in group_user:
        booked_flights_user = Flight.objects.filter(user=user)
        if flight in booked_flights_user:
            flight.user.remove(user)
            flight.book_sum -= 1
            flight.capacity += 1
            flight.income -= flight.price
    group_obj.save()
    flight.save()
    return HttpResponseRedirect('/booksystem/group_info')


def group_remove_member(request, member_id):
    group_obj = Group.objects.get(name=request.user.username)
    user = User.objects.get(pk=member_id)
    group_obj.users.remove(user)
    group_obj.save()
    return HttpResponseRedirect('/booksystem/group_manage')


# 退出登录
def logout_user(request):
    logout(request)
    form = UserForm(request.POST or None)
    context = {
        "form": form,
    }
    return render(request, 'booksystem/login.html', context)


# 登录
def login_user(request):
    if request.method == "POST":
        username = request.POST.get('username', False)
        password = request.POST.get('password', False)
        user = authenticate(username=username, password=password)
        if user is not None:  # 登录成功
            if user.is_active:  # 加载订票页面
                login(request, user)
                context = {
                    'username': request.user.username
                }
                if user.id == ADMIN_ID:
                    # context = admin_finance(request)  # 获取要传入前端的数据
                    return render(request, 'booksystem/admin.html')
                else:
                    if user.pid == 1:
                        return render(request, 'booksystem/result.html', context)
                    else:
                        print("旅行团")
                        context = {
                            'username': "旅行团"
                        }
                        # print("旅行团")
                        return render(request, 'booksystem/tourgroup.html')
            else:
                return render(request, 'booksystem/login.html', {'error_message': 'Your account has been disabled'})
        else:  # 登录失败
            return render(request, 'booksystem/login.html', {'error_message': 'Invalid login'})
    return render(request, 'booksystem/login.html')


# 注册
def register(request):
    form = UserForm(request.POST or None)
    if form.is_valid():
        user = form.save(commit=False)
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user.set_password(password)
        user.save()
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                context = {
                    'username': request.user.username
                }
                if user.pid == 1:
                    return render(request, 'booksystem/result.html', context)  # 注册成功直接render result页面
                else:
                    # 创建一个新的group
                    newgroup = Group(name=request.user.username)
                    newgroup.save()
                    context = {
                        'username': "旅行团"
                    }
                    return render(request, 'booksystem/result.html', context)
    context = {
        "form": form,
    }
    return render(request, 'booksystem/register.html', context)


def tourgroup(request):
    # if request.POST:
    #     if request.POST.has_key('update'):
    #         ...      #update功能实现
    #     else:
    #         ...      #del功能实现
    #     return render(request, 'booksystem/tourgroup.html')
    return render(request, 'booksystem/tourgroup.html')


def group_manage(request):
    if request.POST:
        if 'add' in request.POST:
            # 添加用户
            print(request.POST)
            memberform = MemberInfo(request.POST)
            if memberform.is_valid():
                group_obj = Group.objects.get(name=request.user.username)
                memberid = memberform.cleaned_data.get('member_id')
                membername=memberform.cleaned_data.get('member_name')
                user_obj = User.objects.get(id=memberid)
                if user_obj.username==membername:
                    flag=0
                    if user_obj in group_obj.users.all():
                        flag=1
                    else:
                        group_obj.users.add(user_obj)
                        group_obj.save()
                    # group_obj = Group.objects.get(name=request.user.username)
                    group_user = group_obj.users.all()
                    members = []
                    for member in group_user:
                        members.append(member)
                    if flag==0:
                        context = {
                            'members': members
                        }
                    else:
                        context = {
                            'members': members,
                            'error': "The member already exists"
                        }
                    return render(request, 'booksystem/group_manage.html', context)
                else:
                    group_obj = Group.objects.get(name=request.user.username)
                    group_user = group_obj.users.all()
                    members = []
                    for member in group_user:
                        members.append(member)
                    context = {
                        'members': members,
                        'error':"id and name do not match"
                    }
                    return render(request, 'booksystem/group_manage.html', context)
            else:
                return render(request, 'booksystem/group_manage.html')
        elif request.POST.has_key('del'):
            # 删除用户
            # 用另一种方式实现了
            return render(request, 'booksystem/group_manage.html')
    else:
        # 显示用户
        group_obj = Group.objects.get(name=request.user.username)
        group_user = group_obj.users.all()
        members = []
        for member in group_user:
            members.append(member)
        context = {
            'members': members
        }
        return render(request, 'booksystem/group_manage.html', context)


def result_group(request):
    global global_passenger_ldate
    global global_passenger_lcity
    global global_passenger_acity
    global global_usable_flights_by_atime
    global global_usable_flights_by_ltime
    global global_usable_flights_by_price
    if request.method == 'POST':
        print(request.POST)
        form = PassengerInfoForm(request.POST)  # 绑定数据至表单
        if form.is_valid():
            passenger_lcity = form.cleaned_data.get('leave_city')
            passenger_acity = form.cleaned_data.get('arrive_city')
            passenger_ldate = form.cleaned_data.get('leave_date')
            global_passenger_lcity = passenger_lcity
            global_passenger_acity = passenger_acity
            global_passenger_ldate = passenger_ldate
            # print(type(passenger_ldate))

            # 全设为naive比较
            # china_tz = pytz.timezone('Asia/Shanghai')
            # passenger_ltime = datetime.datetime(
            #     year=passenger_ldate.year,
            #     month=passenger_ldate.month,
            #     day=passenger_ldate.day,
            #     hour=0, minute=0, second=0,
            #     tzinfo=china_tz
            # )

            # 全设为aware比较
            passenger_ltime = datetime.datetime.combine(passenger_ldate, datetime.time())
            print(passenger_ltime)

            # filter 可用航班
            all_flights = Flight.objects.filter(leave_city=passenger_lcity, arrive_city=passenger_acity)
            usable_flights = []
            for flight in all_flights:  # off-set aware
                flight.leave_time = flight.leave_time.replace(tzinfo=None)  # replace方法必须要赋值。。笑哭
                if flight.leave_time.date() == passenger_ltime.date():  # 只查找当天的航班
                    usable_flights.append(flight)

            # 按不同的key排序
            usable_flights_by_ltime = sorted(usable_flights, key=attrgetter('leave_time'))  # 起飞时间从早到晚
            usable_flights_by_atime = sorted(usable_flights, key=attrgetter('arrive_time'))
            usable_flights_by_price = sorted(usable_flights, key=attrgetter('price'))  # 价格从低到高
            global_usable_flights_by_ltime = usable_flights_by_ltime
            global_usable_flights_by_atime = usable_flights_by_atime
            global_usable_flights_by_price = usable_flights_by_price

            # 转换时间格式
            time_format = '%H:%M'
            # for flight in usable_flights_by_ltime:
            #     flight.leave_time = flight.leave_time.strftime(time_format)  # 转成了str
            #     flight.arrive_time = flight.arrive_time.strftime(time_format)
            #
            # for flight in usable_flights_by_atime:
            #     flight.leave_time = flight.leave_time.strftime(time_format)  # 转成了str
            #     flight.arrive_time = flight.arrive_time.strftime(time_format)

            # 虽然只转换了一个list，其实所有的都转换了
            for flight in usable_flights_by_price:
                flight.leave_time = flight.leave_time.strftime(time_format)  # 转成了str
                flight.arrive_time = flight.arrive_time.strftime(time_format)

            # 决定 search_head , search_failure 是否显示
            dis_search_head = 'block'
            dis_search_failure = 'none'
            if len(usable_flights_by_price) == 0:
                dis_search_head = 'none'
                dis_search_failure = 'block'
            context = {
                # 搜多框数据
                'leave_city': passenger_lcity,
                'arrive_city': passenger_acity,
                'leave_date': str(passenger_ldate),
                # 搜索结果
                'usable_flights_by_ltime': usable_flights_by_ltime,
                'usable_flights_by_atime': usable_flights_by_atime,
                'usable_flights_by_price': usable_flights_by_price,
                # 标记
                'dis_search_head': dis_search_head,
                'dis_search_failure': dis_search_failure
            }
            if request.user.is_authenticated:
                context['username'] = request.user.username
            return render(request, 'booksystem/result_group.html', context)  # 最前面如果加了/就变成根目录了，url错误
        else:
            context = {
                'dis_search_head': 'none',
                'dis_search_failure': 'none'
            }
            return render(request, 'booksystem/result_group.html', context)  # 在index界面提交的表单无效，就保持在index界面
    else:
        if global_passenger_acity!=None:
            dis_search_head = 'block'
            dis_search_failure = 'none'
            if len(global_usable_flights_by_price) == 0:
                dis_search_head = 'none'
                dis_search_failure = 'block'
            context = {
                # 搜多框数据
                'leave_city': global_passenger_lcity,
                'arrive_city': global_passenger_acity,
                'leave_date': str(global_passenger_ldate),
                # 搜索结果
                'usable_flights_by_ltime': global_usable_flights_by_ltime,
                'usable_flights_by_atime': global_usable_flights_by_atime,
                'usable_flights_by_price': global_usable_flights_by_price,
                # 标记
                'dis_search_head': dis_search_head,
                'dis_search_failure': dis_search_failure
            }
            return render(request, 'booksystem/result_group.html', context)
        else:
            context = {
                'dis_search_head': 'none',
                'dis_search_failure': 'none'
            }
            return render(request, 'booksystem/result_group.html', context)


@csrf_exempt
def group_book(request, flight_id):
    print("groupbook")
    if not request.user.is_authenticated:  # 如果没登录就render登录页面
        return render(request, 'booksystem/login.html')
    else:
        group_obj = Group.objects.get(name=request.user.username)
        flight = Flight.objects.get(pk=flight_id)
        # 查看乘客已经订购的flights
        booked_flights = group_obj.flight.all()  # 返回 QuerySet
        print(booked_flights)

        if flight in booked_flights:
            context = {
                'username': request.user.username
            }
            return render(request, 'booksystem/group_book_conflict.html', context)

        # book_flight.html 点确认之后，request为 POST 方法，虽然没有传递什么值，但是传递了 POST 信号
        # 确认订票，flight数据库改变

        usernum = 0
        group_user = group_obj.users.all()
        book_user = []  # 可以订票的成员
        for user in group_user:
            booked_flights_user = Flight.objects.filter(user=user)
            if flight not in booked_flights_user:
                book_user.append(user)
                usernum += 1

        # 验证一下，同样的机票只能订一次
        if request.method == 'POST':
            if flight.capacity >= usernum:
                flight.book_sum += usernum
                flight.capacity -= usernum
                flight.income += flight.price * usernum
                group_obj.flight.add(flight)  # 航班加入组
                for user in book_user:
                    flight.user.add(user)
                group_obj.save()
                flight.save()  # 一定要记着save
        # 传递更改之后的票务信息
        context = {
            'flight': flight,
            'username': request.user.username
        }
        return render(request, 'booksystem/group_book.html', context)
    # return render(request, 'booksystem/group_book.html')


def group_info(request):
    if request.user.is_authenticated:
        group_obj = Group.objects.get(name=request.user.username)
        booked_flights = group_obj.flight.all()  # 从 booksystem_flight_user 表过滤出该用户订的航班
        context = {
            'booked_flights': booked_flights,
            'username': request.user.username,  # 导航栏信息更新
        }
        return render(request, 'booksystem/group_info.html', context)
    return render(request, 'booksystem/login.html')  # 用户如果没登录，render登录页面


# 搜索结果页面
def result(request):
    global global_passenger_ldate
    global global_passenger_lcity
    global global_passenger_acity
    global global_usable_flights_by_atime
    global global_usable_flights_by_ltime
    global global_usable_flights_by_price
    if request.method == 'POST':
        print(request.POST)
        form = PassengerInfoForm(request.POST)  # 绑定数据至表单
        if form.is_valid():
            passenger_lcity = form.cleaned_data.get('leave_city')
            passenger_acity = form.cleaned_data.get('arrive_city')
            passenger_ldate = form.cleaned_data.get('leave_date')
            global_passenger_lcity = passenger_lcity
            global_passenger_acity = passenger_acity
            global_passenger_ldate = passenger_ldate
            # print(type(passenger_ldate))

            # 全设为naive比较
            # china_tz = pytz.timezone('Asia/Shanghai')
            # passenger_ltime = datetime.datetime(
            #     year=passenger_ldate.year,
            #     month=passenger_ldate.month,
            #     day=passenger_ldate.day,
            #     hour=0, minute=0, second=0,
            #     tzinfo=china_tz
            # )

            # 全设为aware比较
            passenger_ltime = datetime.datetime.combine(passenger_ldate, datetime.time())
            print(passenger_ltime)

            # filter 可用航班
            all_flights = Flight.objects.filter(leave_city=passenger_lcity, arrive_city=passenger_acity)
            usable_flights = []
            for flight in all_flights:  # off-set aware
                flight.leave_time = flight.leave_time.replace(tzinfo=None)  # replace方法必须要赋值。。笑哭
                if flight.leave_time.date() == passenger_ltime.date():  # 只查找当天的航班
                    usable_flights.append(flight)

            # 按不同的key排序
            usable_flights_by_ltime = sorted(usable_flights, key=attrgetter('leave_time'))  # 起飞时间从早到晚
            usable_flights_by_atime = sorted(usable_flights, key=attrgetter('arrive_time'))
            usable_flights_by_price = sorted(usable_flights, key=attrgetter('price'))  # 价格从低到高
            global_usable_flights_by_ltime = usable_flights_by_ltime
            global_usable_flights_by_atime = usable_flights_by_atime
            global_usable_flights_by_price = usable_flights_by_price

            # 转换时间格式
            time_format = '%H:%M'
            # for flight in usable_flights_by_ltime:
            #     flight.leave_time = flight.leave_time.strftime(time_format)  # 转成了str
            #     flight.arrive_time = flight.arrive_time.strftime(time_format)
            #
            # for flight in usable_flights_by_atime:
            #     flight.leave_time = flight.leave_time.strftime(time_format)  # 转成了str
            #     flight.arrive_time = flight.arrive_time.strftime(time_format)

            # 虽然只转换了一个list，其实所有的都转换了
            for flight in usable_flights_by_price:
                flight.leave_time = flight.leave_time.strftime(time_format)  # 转成了str
                flight.arrive_time = flight.arrive_time.strftime(time_format)

            # 决定 search_head , search_failure 是否显示
            dis_search_head = 'block'
            dis_search_failure = 'none'
            if len(usable_flights_by_price) == 0:
                dis_search_head = 'none'
                dis_search_failure = 'block'
            context = {
                # 搜多框数据
                'leave_city': passenger_lcity,
                'arrive_city': passenger_acity,
                'leave_date': str(passenger_ldate),
                # 搜索结果
                'usable_flights_by_ltime': usable_flights_by_ltime,
                'usable_flights_by_atime': usable_flights_by_atime,
                'usable_flights_by_price': usable_flights_by_price,
                # 标记
                'dis_search_head': dis_search_head,
                'dis_search_failure': dis_search_failure
            }
            if request.user.is_authenticated:
                context['username'] = request.user.username
            return render(request, 'booksystem/result.html', context)  # 最前面如果加了/就变成根目录了，url错误
        else:
            context = {
                'dis_search_head': 'none',
                'dis_search_failure': 'none'
            }
            return render(request, 'booksystem/result.html', context)  # 在index界面提交的表单无效，就保持
    else:
        if global_passenger_acity!=None:
            dis_search_head = 'block'
            dis_search_failure = 'none'
            if len(global_usable_flights_by_price) == 0:
                dis_search_head = 'none'
                dis_search_failure = 'block'
            context = {
                # 搜多框数据
                'leave_city': global_passenger_lcity,
                'arrive_city': global_passenger_acity,
                'leave_date': str(global_passenger_ldate),
                # 搜索结果
                'usable_flights_by_ltime': global_usable_flights_by_ltime,
                'usable_flights_by_atime': global_usable_flights_by_atime,
                'usable_flights_by_price': global_usable_flights_by_price,
                # 标记
                'dis_search_head': dis_search_head,
                'dis_search_failure': dis_search_failure
            }
            return render(request, 'booksystem/result.html', context)
        else:
            context = {
            'dis_search_head': 'none',
            'dis_search_failure': 'none'
        }
        return render(request, 'booksystem/result.html', context)
