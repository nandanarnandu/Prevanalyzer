# Import necessary libraries for data handling, security, and logging
import pandas as pd
import hashlib
import logging
from encryption import EncryptionManager

# Set up logging to track what the program is doing
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        # Initialize empty database and encryption tools
        self.data = None  # Will store employee data
        self.encryption_manager = EncryptionManager()  # Handles encryption/decryption
        self.salary_encrypted = False  # Track if salaries are encrypted

    def process_excel_file(self, filepath):
        """Process uploaded Excel file and store in database"""
        try:
            # Read Excel file into a pandas DataFrame (like a table)
            df = pd.read_excel(filepath)

            # Log the original data for debugging
            logger.info(f"Loading Excel file from {filepath}")
            logger.info(f"Excel file columns: {list(df.columns)}")

            original_data = df.copy()  # Keep a copy of the original data for logging
            logger.info(f"Original data loaded with {len(original_data)} rows and columns: {list(original_data.columns)}")
            logger.info(f"Loaded Excel file with {len(df)} rows")
            
            # Check if all required columns are present
            required_columns = ['id', 'name', 'phone_number', 'email', 'salary']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return f"❌ Missing required columns: {', '.join(missing_columns)}\n\nFound columns: {list(df.columns)}"
            
            # Remove rows with empty data
            df = df.dropna()
            logger.info(f"After removing empty rows: {len(df)} rows")

            try:
                # Convert columns to correct data types (numbers, text, etc.)
                df['id'] = df['id'].astype(int)
                df['salary'] = pd.to_numeric(df['salary'], errors='coerce')
                df['phone_number'] = df['phone_number'].astype(str)
                df['name'] = df['name'].astype(str)
                df['email'] = df['email'].astype(str)
            except Exception as e:
                logger.error(f"Error converting data types: {e}")
                return f"❌ Error processing data types: {str(e)}"

            # Remove rows where salary couldn't be converted to number
            df = df.dropna(subset=['salary'])
            logger.info(f"After cleaning: {len(df)} valid rows")

            # Check if we have any data left after cleaning
            if df.empty:
                return "❌ No valid data to store after processing the Excel file."

            # Store the cleaned data
            return self.store_employee_data(original_data, encrypt_salary=False)

        except Exception as e:
            logger.error(f"File processing error: {e}")
            return f"❌ Error processing file: {str(e)}"

    def store_employee_data(self, df, encrypt_salary=False):
        """Store employee data in memory database"""
        try:
            # Save the data to our database (in computer memory)
            self.data = df.copy()  # Store a copy of the DataFrame
            # logger.info(f"Stored {len(df)} employee records with columns: {list(df.columns})")
            self.salary_encrypted = False

            # Encrypt salaries if requested
            if encrypt_salary:
                self.encrypt_salaries()

            return f"✅ Successfully stored {len(df)} employee records!"
        except Exception as e:
            logger.error(f"Error storing data: {e}")
            return f"❌ Error storing data: {str(e)}"

    def get_all_employees(self):
        """Get all employee records"""
        # Return a copy of all employee data if it exists
        if self.data is not None:
            return self.data.copy()
        return None

    def encrypt_salaries(self):
        """Encrypt all salary data"""
        # Convert all salary numbers into encrypted (scrambled) text for security
        if self.data is not None and not self.salary_encrypted:
            try:
                self.data['salary'] = self.data['salary'].apply(
                    lambda x: self.encryption_manager.encrypt_value(x)
                )
                self.salary_encrypted = True
                return "✅ All salary data has been encrypted successfully!"
            except Exception as e:
                logger.error(f"Encryption error: {e}")
                return f"❌ Error encrypting salaries: {str(e)}"
        elif self.salary_encrypted:
            return "ℹ️ Salary data is already encrypted."
        else:
            return "❌ No data available to encrypt."

    def decrypt_salaries(self):
        """Decrypt all salary data"""
        # Convert encrypted salary text back to readable numbers
        if self.data is not None and self.salary_encrypted:
            try:
                self.data['salary'] = self.data['salary'].apply(
                    lambda x: self.encryption_manager.decrypt_value(x)
                )
                self.data['salary'] = pd.to_numeric(self.data['salary'], errors='coerce')
                self.salary_encrypted = False
                return "✅ All salary data has been decrypted successfully!"
            except Exception as e:
                logger.error(f"Decryption error: {e}")
                return f"❌ Error decrypting salaries: {str(e)}"
        elif not self.salary_encrypted:
            return "ℹ️ Salary data is not encrypted."
        else:
            return "❌ No data available to decrypt."

    def hash_email(self):
        """Hash email addresses"""
        # Convert email addresses to scrambled text that can't be reversed
        if self.data is not None:
            try:
                self.data['email'] = self.data['email'].apply(
                    lambda x: hashlib.sha256(x.encode()).hexdigest()
                )
                return "✅ Email addresses hashed successfully!"
            except Exception as e:
                logger.error(f"Hashing error: {e}")
                return f"❌ Error hashing emails: {str(e)}"
        return "❌ No data available to hash."

    def mask_phone_numbers(self):
        """Mask phone numbers by hiding middle digits"""
        # Hide most digits in phone numbers, showing only first 2 and last 2
        if self.data is not None:
            try:
                self.data['phone_number'] = self.data['phone_number'].apply(
                    lambda x: f"{x[:2]}******{x[-2:]}" if len(x) >= 4 else x
                )
                return "✅ Phone numbers masked successfully!"
            except Exception as e:
                logger.error(f"Masking error: {e}")
                return f"❌ Error masking phone numbers: {str(e)}"
        return "❌ No data available to mask."

    def tokenize_names(self):
        """Tokenize names to generic identifiers"""
        # Replace all real names with generic labels like "user_1", "user_2"
        if self.data is not None:
            try:
                self.data['name'] = [f"user_{i+1}" for i in range(len(self.data))]
                return "✅ Names tokenized successfully!"
            except Exception as e:
                logger.error(f"Tokenization error: {e}")
                return f"❌ Error tokenizing names: {str(e)}"
        return "❌ No data available to tokenize."

    def apply_all_privacy_techniques(self):
        """Apply all privacy techniques"""
        # Run all privacy protection methods at once
        messages = []
        messages.append(self.encrypt_salaries())
        messages.append(self.hash_email())
        messages.append(self.mask_phone_numbers())
        messages.append(self.tokenize_names())
        return "\n".join(messages)

    def search_employees(self, search_term):
        """Search for employees by name, email, or phone"""
        # Find employees whose name, email, or phone contains the search term
        if self.data is None:
            return None
        try:
            search_term = search_term.lower()
            mask = (
                self.data['name'].str.lower().str.contains(search_term, na=False) |
                self.data['email'].str.lower().str.contains(search_term, na=False) |
                self.data['phone_number'].astype(str).str.contains(search_term, na=False)
            )
            results = self.data[mask]
            return results if not results.empty else None
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None

    def get_statistics(self):
        """Get database statistics"""
        # Calculate and return summary information about the data
        if self.data is None:
            return "❌ No data available for statistics."

        try:
            # If salaries are encrypted, show limited stats
            if self.salary_encrypted:
                stats = {
                    'total_employees': len(self.data),
                    'salary_status': '🔐 Encrypted',
                    'records_with_email': self.data['email'].notna().sum(),
                    'records_with_phone': self.data['phone_number'].notna().sum(),
                    'note': 'Decrypt salaries to view salary statistics.'
                }
            else:
                # If salaries are not encrypted, show detailed salary stats
                salary_stats = self.data['salary'].describe()
                stats = {
                    'total_employees': len(self.data),
                    'salary_status': '🔓 Not Encrypted',
                    'average_salary': f"${salary_stats['mean']:.2f}",
                    'median_salary': f"${salary_stats['50%']:.2f}",
                    'min_salary': f"${salary_stats['min']:.2f}",
                    'max_salary': f"${salary_stats['max']:.2f}",
                    'salary_std_dev': f"${salary_stats['std']:.2f}",
                    'records_with_email': self.data['email'].notna().sum(),
                    'records_with_phone': self.data['phone_number'].notna().sum()
                }
            return stats
        except Exception as e:
            logger.error(f"Statistics error: {e}")
            return f"❌ Error calculating statistics: {str(e)}"