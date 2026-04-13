# LiveKit Agent System Documentation

This folder contains documentation about our LiveKit voice agent system.

## 📚 Documentation Guide

### Start Here
1. **[WORKER_LIFECYCLE_GUIDE.md](./WORKER_LIFECYCLE_GUIDE.md)** - **Start with this!**
   - Beginner-friendly explanation
   - No code overload
   - Clear step-by-step lifecycle
   - Analogies and simple concepts

### Technical Deep Dives
2. **[ACTUAL_IMPLEMENTATION_GUIDE.md](./ACTUAL_IMPLEMENTATION_GUIDE.md)**
   - Complete technical implementation
   - Extensive code examples with file references
   - Database models and API endpoints
   - Error handling and recovery mechanisms

3. **[INTERNAL_WORKING_OF_AGENT.md](./INTERNAL_WORKING_OF_AGENT.md)**
   - Deep dive into LiveKit framework internals
   - How LiveKit agents work under the hood
   - 1,200+ lines of detailed framework analysis


## 🎯 Which Document Should I Read?

- **New to the project?** → Start with WORKER_LIFECYCLE_GUIDE.md
- **Need to understand the code?** → Read ACTUAL_IMPLEMENTATION_GUIDE.md
- **Debugging LiveKit issues?** → Check INTERNAL_WORKING_OF_AGENT.md

## 🔑 Key Concepts

- **Worker**: Single Python process handling all conversations
- **Agent**: Individual conversation handler for each user
- **Persona**: AI personality with knowledge and voice
- **Orchestrator**: Manager ensuring worker health