# Ansible Demo Project

This project demonstrates Ansible automation capabilities with a simple setup that includes webserver and database roles. It's designed to run without requiring sudo/root privileges, making it easy to test and learn Ansible concepts.

## Project Structure

```
ansible/
├── ansible.cfg              # Ansible configuration
├── group_vars/              # Variables applied to groups of hosts
│   └── all.yml              # Variables for all hosts
├── inventory/               # Inventory files
│   └── hosts                # Host definitions
├── roles/                   # Role definitions
│   ├── database/            # Database role
│   │   ├── tasks/           # Database tasks
│   │   ├── templates/       # Database templates
│   │   └── vars/            # Database variables
│   └── webserver/           # Webserver role
│       ├── handlers/        # Webserver handlers
│       ├── tasks/           # Webserver tasks
│       ├── templates/       # Webserver templates
│       └── vars/            # Webserver variables
└── site.yml                 # Main playbook
```

## Prerequisites

- Ansible 2.18.1 or higher
- Linux environment (tested on Ubuntu 25.04)

## Features

This Ansible project demonstrates:

1. **Role-based organization** - Separating tasks into webserver and database roles
2. **Variable management** - Using role-specific and global variables
3. **Template rendering** - Creating configuration files from templates
4. **Conditional execution** - Skipping tasks based on conditions
5. **File operations** - Creating directories and files
6. **Command execution** - Running shell commands when needed

## Roles

### Webserver Role

The webserver role simulates setting up a web server by:

- Checking if Nginx is installed
- Creating a web content directory
- Generating an HTML file from a template
- Creating an Nginx configuration file

### Database Role

The database role simulates setting up a database server by:

- Checking if SQLite is installed
- Creating a database directory
- Setting up a test database
- Initializing the database schema

## Running the Project

To run the Ansible playbook:

```bash
cd ansible
ansible-playbook -i inventory/hosts site.yml
```

## Output

The playbook will create the following structure in your home directory:

```
~/ansible_demo/
├── db/                      # Database files
│   ├── schema.sql           # Database schema
│   └── test.db              # SQLite database
├── nginx.conf               # Nginx configuration
└── www/                     # Web content
    └── index.html           # Demo HTML page
```

## Notes

- This project is designed to run without sudo privileges
- It uses local connections for demonstration purposes
- The playbook will check for installed software but won't attempt to install anything
- All files are created in the user's home directory under `~/ansible_demo/`

## Customization

You can modify the following files to customize the project:

- `roles/webserver/vars/main.yml` - Change website title and server name
- `roles/database/vars/main.yml` - Modify database name and credentials
- `roles/webserver/templates/index.html.j2` - Edit the HTML template
- `roles/database/templates/schema.sql.j2` - Modify the database schema

## Troubleshooting

If you encounter any issues:

1. Ensure Ansible is installed: `ansible --version`
2. Check that the playbook can be parsed: `ansible-playbook --syntax-check site.yml`
3. Run with increased verbosity: `ansible-playbook -vvv -i inventory/hosts site.yml`
4. Verify file permissions in your home directory

## License

This project is open source and available for educational purposes.

## Last Updated

June 11, 2025
