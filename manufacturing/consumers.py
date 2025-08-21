import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import SerialNumber, ProcessRecord, ProductionAlert


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications"""
    
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.group_name = "notifications"
        
        # Join notification group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave notification group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
            
        except json.JSONDecodeError:
            pass
    
    async def notification_message(self, event):
        """Send notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event['message'],
            'alert_type': event.get('alert_type', 'info'),
            'timestamp': event.get('timestamp')
        }))
    
    async def process_update(self, event):
        """Send process update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'process_update',
            'serial_number': event['serial_number'],
            'operation': event['operation'],
            'status': event['status'],
            'user': event['user'],
            'timestamp': event.get('timestamp')
        }))


class DashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for dashboard real-time updates"""
    
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.group_name = "dashboard"
        
        # Join dashboard group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial dashboard data
        dashboard_data = await self.get_dashboard_data()
        await self.send(text_data=json.dumps({
            'type': 'dashboard_data',
            'data': dashboard_data
        }))
    
    async def disconnect(self, close_code):
        # Leave dashboard group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'refresh_dashboard':
                dashboard_data = await self.get_dashboard_data()
                await self.send(text_data=json.dumps({
                    'type': 'dashboard_data',
                    'data': dashboard_data
                }))
            
        except json.JSONDecodeError:
            pass
    
    async def dashboard_update(self, event):
        """Send dashboard update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': event['data']
        }))
    
    @database_sync_to_async
    def get_dashboard_data(self):
        """Get current dashboard statistics"""
        from django.db.models import Count
        
        total_serials = SerialNumber.objects.count()
        status_counts = SerialNumber.objects.values('status').annotate(count=Count('id'))
        active_alerts = ProductionAlert.objects.filter(
            is_active=True, is_resolved=False
        ).count()
        
        return {
            'total_serials': total_serials,
            'status_counts': list(status_counts),
            'active_alerts': active_alerts,
            'timestamp': str(timezone.now())
        }
