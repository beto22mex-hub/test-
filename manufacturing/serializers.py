from rest_framework import serializers
from serials.models import SerialNumber, AuthorizedPart
from operations.models import Operation, ProcessRecord
from analytics.models import ProductionAlert
from operators.models import UserProfile


class AuthorizedPartSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorizedPart
        fields = ['id', 'part_number', 'description', 'revision', 'is_active', 'created_at']


class OperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Operation
        fields = [
            'id', 'name', 'description', 'sequence_number', 
            'estimated_time_minutes', 'requires_approval', 'is_active'
        ]


class ProcessRecordSerializer(serializers.ModelSerializer):
    operation_name = serializers.CharField(source='operation.name', read_only=True)
    operation_sequence = serializers.IntegerField(source='operation.sequence_number', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.get_full_name', read_only=True)
    
    class Meta:
        model = ProcessRecord
        fields = [
            'id', 'operation', 'operation_name', 'operation_sequence',
            'status', 'processed_by', 'processed_by_name', 'started_at', 
            'completed_at', 'notes', 'quality_check_passed', 'created_at'
        ]


class SerialNumberSerializer(serializers.ModelSerializer):
    authorized_part_info = AuthorizedPartSerializer(source='authorized_part', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    completion_percentage = serializers.ReadOnlyField()
    current_operation_name = serializers.CharField(source='current_operation.name', read_only=True)
    process_records = ProcessRecordSerializer(many=True, read_only=True)
    
    class Meta:
        model = SerialNumber
        fields = [
            'id', 'serial_number', 'order_number', 'authorized_part', 
            'authorized_part_info', 'status', 'created_by', 'created_by_name',
            'completion_percentage', 'current_operation_name', 'process_records',
            'created_at', 'updated_at', 'completed_at'
        ]


class ProductionAlertSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    serial_number_display = serializers.CharField(source='serial_number.serial_number', read_only=True)
    
    class Meta:
        model = ProductionAlert
        fields = [
            'id', 'title', 'message', 'alert_type', 'priority',
            'serial_number', 'serial_number_display', 'is_active', 'is_resolved',
            'created_by', 'created_by_name', 'resolved_by', 'resolved_by_name',
            'created_at', 'resolved_at'
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'username', 'full_name', 'email',
            'employee_id', 'role', 'department', 'phone',
            'is_active_operator', 'can_approve_operations',
            'can_generate_serials', 'can_view_statistics', 'can_manage_users'
        ]
