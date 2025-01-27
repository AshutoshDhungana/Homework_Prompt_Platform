from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create database connection
engine = create_engine(os.getenv('DATABASE_URL'))

# SQL to modify the role column
migration_sql = """
-- First, remove the existing check constraint
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;

-- Create the enum type if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
        CREATE TYPE userrole AS ENUM ('teacher', 'student');
    END IF;
END$$;

-- Alter the role column to use the new enum type
ALTER TABLE users 
    ALTER COLUMN role TYPE userrole 
    USING role::userrole;

-- Add NOT NULL constraint if it doesn't exist
ALTER TABLE users 
    ALTER COLUMN role SET NOT NULL;
"""

def run_migration():
    try:
        with engine.connect() as connection:
            connection.execute(text(migration_sql))
            connection.commit()
            print("Migration completed successfully!")
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        raise

if __name__ == "__main__":
    run_migration() 