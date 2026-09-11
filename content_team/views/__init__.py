from content_team.views.order_views import standalone_order_step1, load_teams_by_service, load_plans_by_team, standalone_order_step2, standalone_order_step3
from content_team.views.order import team_orders_list, team_order_detail, accept_order, reject_order, deliver_order, accept_revision, reject_revision
from content_team.views.api import check_slug_availability, submit_team_review_ajax, edit_team_review_ajax, standalone_apply_discount
from content_team.views.member import team_members_manage, team_member_edit, team_join_request_handle, team_manage_view
from content_team.views.coupon import team_coupons, team_coupon_create, team_coupon_edit, team_coupon_delete
from content_team.views.dashboard import content_team_dashboard, team_performance_report, plans_dashboard
from content_team.views.plan import service_plans_management, create_plan, edit_plan, delete_plan
from content_team.views.team import team_list_view, team_detail_view, plan_detail
from content_team.views.content_order_views import content_orders_list, content_order_detail, delete_content_order
