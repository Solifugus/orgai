# OrgAI Presentation Guide

## Demonstration Prompts

### 1. Policy Document Integration
```bash
"Compare our vacation and remote work policies. What are the key differences in terms of:
- Advance notice requirements
- Approval process
- Maximum duration
- Documentation needed"
```

### 2. Database Integration (with real SQL Server)
```bash
"Analyze our employee database structure and tell me:
- What are the main tables and their relationships?
- How is employee data organized across different databases?
- What stored procedures are available for HR operations?"
```

### 3. Cross-Reference Capabilities
```bash
"Based on our policies and database structure, what would be the complete process for:
- Requesting a vacation
- Getting it approved
- Recording it in the system
- Managing workload during absence"
```

### 4. Technical Documentation Integration
```bash
"Explain the process for:
- Submitting an expense report
- Requesting IT support
- Accessing company resources remotely
Include any relevant forms, systems, or approval steps needed"
```

### 5. Compliance and Policy Analysis
```bash
"What are our key compliance requirements for:
- Data security
- Employee privacy
- Remote work
- Record keeping
And how are these enforced through our systems?"
```

### 6. System Integration Demonstration
```bash
"When an employee requests remote work:
- What policies apply?
- What systems need to be updated?
- What approvals are required?
- What documentation is needed?"
```

### 7. Data Analysis Capabilities
```bash
"Based on our database structure and policies:
- How do we track employee time off?
- What reports can we generate about employee attendance?
- How can we analyze patterns in leave requests?"
```

### 8. Policy Impact Analysis
```bash
"If we were to change our remote work policy to require 2 weeks notice:
- What systems would need to be updated?
- What documentation would need to be modified?
- What approval workflows would be affected?"
```

### 9. Comprehensive Workflow Example
```bash
"Walk me through the complete process of an employee:
1. Requesting a vacation
2. Getting it approved
3. Recording it in the system
4. Managing their workload
5. Returning to work
Include all relevant policies, systems, and documentation needed at each step"
```

### 10. System Integration Test
```bash
"Show me how our different systems work together by explaining:
- How policy changes are reflected in our databases
- How employee requests flow through our systems
- How compliance is maintained across platforms"
```

## Presentation Tips

### Suggested Flow
1. **Introduction (5 minutes)**
   - Brief overview of OrgAI
   - Key features and benefits
   - Current integration status

2. **Basic Functionality (10 minutes)**
   - Start with simple policy questions
   - Show how it understands and synthesizes information
   - Demonstrate response quality and context awareness

3. **Technical Capabilities (10 minutes)**
   - Database integration (mock data fallback)
   - Policy document integration
   - System-wide integration

4. **Advanced Features (10 minutes)**
   - Cross-referencing capabilities
   - Workflow analysis
   - Impact assessment

5. **Q&A and Discussion (15 minutes)**
   - Address specific use cases
   - Discuss implementation details
   - Gather feedback

### Key Points to Highlight
1. **Flexibility**
   - Works with or without SQL Server
   - Adapts to different environments
   - Graceful fallback mechanisms

2. **Integration**
   - Seamless connection between policies and systems
   - Automatic updates and caching
   - Consistent behavior across environments

3. **Practical Benefits**
   - Reduced manual work
   - Improved compliance
   - Better decision support

4. **Technical Advantages**
   - Easy setup and maintenance
   - Robust error handling
   - Scalable architecture

### Troubleshooting Tips
- If server fails to start: `pkill -f "uvicorn server:app"`
- If database connection fails: Check ODBC driver installation
- If policy documents don't update: Verify internet connectivity

### Environment Setup
```bash
# Start the server
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Kill existing process if needed
pkill -f "uvicorn server:app"
```

## Backup Plan
If live demonstration faces issues:
1. Have screenshots ready
2. Prepare example responses
3. Show system architecture diagram
4. Demonstrate mock data functionality 