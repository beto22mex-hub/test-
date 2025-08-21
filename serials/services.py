from django.db import transaction
from django.contrib.auth.models import User
from .models import SerialNumber, AuthorizedPart
import re
from datetime import datetime


class SerialNumberGenerator:
    @staticmethod
    def get_year_letter(year):
        """Convert year to letter (K=2025, L=2026, etc.)"""
        # K = 2025, so year 2025 = K (75th letter from A)
        base_year = 2025
        if year < base_year:
            raise ValueError(f"Año {year} no soportado. Año mínimo: {base_year}")
        
        year_offset = year - base_year
        if year_offset > 25:  # Only support A-Z (26 letters)
            raise ValueError(f"Año {year} excede el rango soportado")
        
        return chr(ord('K') + year_offset)
    
    @staticmethod
    def get_month_letter(month):
        """Convert month to letter (A=enero, B=febrero, etc.)"""
        if month < 1 or month > 12:
            raise ValueError(f"Mes {month} inválido")
        
        return chr(ord('A') + month - 1)
    
    @staticmethod
    def generate_serial_number(order_number, part_number, created_by):
        """Generate a new serial number with [YEAR][MONTH]###-###M format"""
        with transaction.atomic():
            # Get the authorized part
            try:
                authorized_part = AuthorizedPart.objects.get(
                    part_number=part_number,
                    is_active=True
                )
            except AuthorizedPart.DoesNotExist:
                raise ValueError(f"Componente autorizado {part_number} no encontrado o inactivo")
            
            # Get current date
            now = datetime.now()
            year_letter = SerialNumberGenerator.get_year_letter(now.year)
            month_letter = SerialNumberGenerator.get_month_letter(now.month)
            
            # Find the next available serial number for current year/month
            prefix = f"{year_letter}{month_letter}"
            last_serial = SerialNumber.objects.filter(
                serial_number__startswith=prefix
            ).order_by('-serial_number').first()
            
            if last_serial:
                # Extract numbers from last serial ([YEAR][MONTH]###-###M)
                pattern = f'{prefix}(\\d{{3}})-(\\d{{3}})M'
                match = re.match(pattern, last_serial.serial_number)
                if match:
                    first_num = int(match.group(1))
                    second_num = int(match.group(2))
                    
                    # Increment second number, reset to first+1 if second reaches 999
                    if second_num < 999:
                        second_num += 1
                    else:
                        first_num += 1
                        second_num = 1
                        
                        if first_num > 999:
                            raise ValueError("Se ha alcanzado el límite máximo de números de serie para este mes")
                else:
                    first_num = 1
                    second_num = 1
            else:
                first_num = 1
                second_num = 1
            
            # Format the serial number: [YEAR][MONTH]###-###M
            serial_number = f"{prefix}{first_num:03d}-{second_num:03d}M"
            
            # Create the serial number record
            serial = SerialNumber.objects.create(
                serial_number=serial_number,
                order_number=order_number,
                authorized_part=authorized_part,
                created_by=created_by,
                status='CREATED'
            )
            
            return serial


class SerialNumberValidator:
    @staticmethod
    def validate_serial_format(serial_number):
        """Validate new serial number format [YEAR][MONTH]###-###M"""
        pattern = r'^[K-Z][A-L]\d{3}-\d{3}M$'
        return bool(re.match(pattern, serial_number))
    
    @staticmethod
    def validate_order_number(order_number):
        """Validate order number format and requirements"""
        if not order_number:
            raise ValueError("El número de orden es requerido")
        
        if len(order_number) < 3:
            raise ValueError("El número de orden debe tener al menos 3 caracteres")
        
        # Add more validation rules as needed
        return True
    
    @staticmethod
    def check_order_duplicates(order_number):
        """Check if order number already has serial numbers"""
        return SerialNumber.objects.filter(order_number=order_number).exists()
    
    @staticmethod
    def decode_serial_info(serial_number):
        """Decode information from serial number"""
        if not SerialNumberValidator.validate_serial_format(serial_number):
            return None
        
        year_letter = serial_number[0]
        month_letter = serial_number[1]
        
        # Decode year (K=2025, L=2026, etc.)
        year = 2025 + (ord(year_letter) - ord('K'))
        
        # Decode month (A=1, B=2, etc.)
        month = ord(month_letter) - ord('A') + 1
        
        # Extract sequence numbers
        pattern = r'^[K-Z][A-L](\d{3})-(\d{3})M$'
        match = re.match(pattern, serial_number)
        if match:
            first_seq = int(match.group(1))
            second_seq = int(match.group(2))
        else:
            first_seq = 0
            second_seq = 0
        
        return {
            'year': year,
            'month': month,
            'first_sequence': first_seq,
            'second_sequence': second_seq,
            'year_letter': year_letter,
            'month_letter': month_letter
        }
