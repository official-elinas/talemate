
def game(TM):
    
    MSG_PROCESSED_INSTRUCTIONS = "Simulation suite processed instructions"
    
    MSG_HELP = "Instructions to the simulation computer are only process if the computer is addressed at the beginning of the instruction. Please state your commands by addressing the computer by stating \"Computer,\" followed by an instruction. For example ... \"Computer, i want to experience being on a derelict spaceship.\""
    
    PROMPT_NARRATE_ROUND = "Narrate the simulation and reveal some new details to the player in one paragraph."
    
    PROMPT_ANSWER_QUESTION = "The computer calls the following function:\n\n{call}\n\nand answers the player's question."
    
    PROMPT_STARTUP = "Narrate the computer asking the user to state the nature of their desired simulation."
    
    CTX_PIN_UNAWARE = "Characters in the simulation ARE NOT AWARE OF THE COMPUTER."
    
    class SimulationSuite:
        
        def __init__(self):
            # do we update the world state at the end of the round
            self.update_world_state = False
            
            self.simulation_reset = False
            
            TM.log.debug("SIMULATION SUITE INIT...")
            
            self.player_character = TM.scene.get_player_character()
            self.player_message = TM.scene.last_player_message()
            self.last_processed_call = TM.game_state.get_var("instr.lastprocessed_call", -1)
            self.player_message_is_instruction = (
                self.player_message and
                self.player_message.raw.lower().startswith("computer") and
                not self.player_message.hidden and
                not self.last_processed_call > self.player_message.id
            )
            
        
        def run(self):
            if not TM.game_state.has_var("instr.simulation_stopped"):
                self.simulation()
            
            self.finalize_round()
            
        def simulation(self):
            
            if not TM.game_state.has_var("instr.simulation_started"):
                self.startup()
            else:
                self.simulation_calls()
                
            if self.update_world_state:
                self.run_update_world_state(force=True)
                
            
        def startup(self):
            TM.emit_status("busy", "Simulation suite powering up.", as_scene_message=True)
            TM.game_state.set_var("instr.simulation_started", "yes", commit=False)
            TM.agents.narrator.action_to_narration(
                action_name="progress_story",
                narrative_direction=PROMPT_STARTUP,
                emit_message=False
            )
            TM.agents.narrator.action_to_narration(
                action_name="passthrough",
                narration=MSG_HELP
            )
            TM.agents.world_state.manager(
                action_name="save_world_entry",
                entry_id="sim.quarantined",
                text=CTX_PIN_UNAWARE,
                meta={},
                pin=True
            )
            TM.game_state.set_var("instr.simulation_started", "yes", commit=False)
            TM.emit_status("success", "Simulation suite ready", as_scene_message=True)
            self.update_world_state = True
            
        def simulation_calls(self):
            """
            Calls the simulation suite main prompt to determine the appropriate
            simulation calls
            """
            
            if not self.player_message_is_instruction:
                return
            
            TM.game_state.set_var("instr.has_issued_instructions", "yes", commit=False)
            
            calls = TM.client.render_and_request(
                "computer",
                dedupe_enabled=False,
                player_instruction=self.player_message.raw,
                scene=TM.scene,
            )
            
            calls = calls.split("\n")
            
            TM.log.debug("SIMULATION SUITE CALLS", callse=calls)
            
            # calls that are processed
            processed = []
            
            for call in calls:
                processed_call = self.process_call(call)
                if processed_call:
                    processed.append(processed_call)
            
            """
            {% set _ = emit_status("busy", "Simulation suite altering environment.", as_scene_message=True) %}
            {% set update_world_state = True %}
            {% set _ = agent_action("narrator", "action_to_narration", action_name="progress_story", narrative_direction="The computer calls the following functions:\n"+processed.join("\n")+"\nand the simulation adjusts the environment according to the user's wishes.\n\nWrite the narrative that describes the changes to the player in the context of the simulation starting up.", emit_message=True) %}
            """
            
            TM.emit_status("busy", "Simulation suite altering environment.", as_scene_message=True)
            compiled = "\n".join(processed)
            if not self.simulation_reset:
                TM.agents.narrator.action_to_narration(
                    action_name="progress_story",
                    narrative_direction=f"The computer calls the following functions:\n\n{compiled}\n\nand the simulation adjusts the environment according to the user's wishes.\n\nWrite the narrative that describes the changes to the player in the context of the simulation starting up.",
                    emit_message=True
                )
            self.update_world_state = True
            
            
        def process_call(self, call:str) -> str:
            """
            Processes a simulation call
            
            Simulation alls are pseudo functions that are called by the simulation suite
            
            We grab the function name by splitting against ( and taking the first element
            if the SimulationSuite has a method with the name _call_{function_name} then we call it
            
            if a function name could be found but we do not have a method to call we dont do anything
            but we still return it as procssed as the AI can still interpret it as something later on
            """
            
            if "(" not in call:
                return None
            
            function_name = call.split("(")[0]
            
            if hasattr(self, f"call_{function_name}"):
                TM.log.debug("SIMULATION SUITE CALL", call=call, function_name=function_name)
                
                inject = f"The computer executes the function `{call}`"
                
                return getattr(self, f"call_{function_name}")(call, inject)
            
            return call
        
        
        def call_set_simulation_goal(self, call:str, inject:str) -> str:
            """
            Set's the simulation goal as a permanent pin
            """
            TM.emit_status("busy", "Simulation suite setting goal.", as_scene_message=True)
            TM.agents.world_state.manager(
                action_name="save_world_entry",
                entry_id="sim.goal",
                text=self.player_message.raw,
                meta={},
                pin=True
            )
            return call
        
        def call_change_environment(self, call:str, inject:str) -> str:
            """
            Simulation changes the environment, this is entirely interpreted by the AI
            and we dont need to do any logic on our end, so we just return the call
            """
            return call
        
        
        def call_answer_question(self, call:str, inject:str) -> str:
            """
            The player asked the simulation a query, we need to process this and have
            the AI produce an answer
            """
            
            TM.narrator.action_to_narration(
                action_name="progress_story",
                narrative_direction=PROMPT_ANSWER_QUESTION.format(call=call),
                emit_message=True
            )
        
        
        def call_set_player_persona(self, call:str, inject:str) -> str:
            
            """
            The simulation suite is altering the player persona
            """
            
            TM.emit_status("busy", "Simulation suite altering user persona.", as_scene_message=True)
            character_attributes = TM.agents.world_state.extract_character_sheet(
                name=self.player_character.name, text=inject, alteration_instructions=self.player_message.raw
            )
            self.player_character.update(base_attributes=character_attributes)
            
            character_description = TM.agents.creator.determine_character_description(character=self.player_character)
            self.player_character.update(description=character_description)
            TM.log.debug("SIMULATION SUITE: transform player", attributes=character_attributes, description=character_description)
            
            return call


        def call_set_player_name(self, call:str, inject:str) -> str:
            
            """
            The simulation suite is altering the player name
            """
            
            TM.emit_status("busy", "Simulation suite adjusting user identity.", as_scene_message=True)
            character_name = TM.agents.creator.determine_character_name(character_name=f"{inject} - What is a fitting name for the player persona? Respond with the current name if it still fits.")
            TM.log.debug("SIMULATION SUITE: player name", character_name=character_name)
            if character_name != self.player_character.name:
                self.player_character.rename(character_name)
                
            return call


        def call_add_ai_character(self, call:str, inject:str) -> str:
            TM.emit_status("busy", "Simulation suite adding character.", as_scene_message=True)
            
            character_name = TM.agents.creator.determine_character_name(character_name=f"{inject} - what is the name of the character to be added to the scene? If no name can extracted from the text, extract a short descriptive name instead. Respond only with the name.")
            
            TM.emit_status("busy", f"Simulation suite adding character: {character_name}", as_scene_message=True)
            
            TM.log.debug("SIMULATION SUITE: add npc", name=character_name)
            
            npc = TM.agents.director.persist_character(name=character_name, content=self.player_message.raw)
            
            TM.agents.world_state.manager(
                action_name="add_detail_reinforcement",
                character_name=npc.name,
                question="Goal",
                instructions=f"Generate a goal for {npc.name}, based on the user's chosen simulation",
                interval=25,
                run_immediately=True
            )
            
            TM.log.debug("SIMULATION SUITE: added npc", npc=npc)
            
            TM.agents.visual.generate_character_portrait(character_name=npc.name)
            
            return call        


        def call_remove_ai_character(self, call:str, inject:str) -> str:
            TM.emit_status("busy", "Simulation suite removing character.", as_scene_message=True)
            
            character_name = TM.agents.creator.determine_character_name(character_name=f"{inject} - what is the name of the character being removed?", allowed_names=TM.scene.npc_character_names())
            
            npc = TM.scene.get_character(character_name)
            
            if npc:
                TM.log.debug("SIMULATION SUITE: remove npc", npc=npc.name)
                TM.agents.world_state.manager(action_name="deactivate_character", character_name=npc.name)
            
            return call

        def call_change_ai_character(self, call:str, inject:str) -> str:
            TM.emit_status("busy", "Simulation suite altering character.", as_scene_message=True)
            
            character_name = TM.agents.creator.determine_character_name(character_name=f"{inject} - what is the name of the character receiving the changes (before the change)?", allowed_names=TM.scene.npc_character_names())
            
            character_name_after = TM.agents.creator.determine_character_name(character_name=f"{inject} - what is the name of the character receiving the changes (after the changes)?")
            
            npc = TM.scene.get_character(character_name)
            
            if npc:
                TM.emit_status("busy", f"Changing {character_name} -> {character_name_after}", as_scene_message=True)
                
                TM.log.debug("SIMULATION SUITE: transform npc", npc=npc)
                
                character_attributes = TM.agents.world_state.extract_character_sheet(name=npc.name, alteration_instructions=self.player_message.raw)
                
                npc.update(base_attributes=character_attributes)
                character_description = TM.agents.creator.determine_character_description(character=npc)
                
                npc.update(description=character_description)
                TM.log.debug("SIMULATION SUITE: transform npc", attributes=character_attributes, description=character_description)
                
                if character_name_after != character_name:
                    npc.rename(character_name_after)
                    
            return call
        
        def call_end_simulation(self, call:str, inject:str) -> str:
            
            explicit_command = TM.client.query_text_eval("has the player explicitly asked to end the simulation?", self.player_message.raw)
            
            if explicit_command:
                TM.emit_status("busy", "Simulation suite ending current simulation.", as_scene_message=True)
                TM.agents.narrator.action_to_narration(
                    action_name="progress_story",
                    narrative_direction=f"The computer ends the simulation, dissolving the environment and all artificial characters, erasing all memory of it and finally returning the player to the inactive simulation suite. List of artificial characters: {', '.join(TM.scene.npc_character_names())}. The player is also transformed back to their normal persona.",
                    emit_message=True
                )
                TM.scene.restore()
                self.simulation_reset = True

        def finalize_round(self):
            
            if self.update_world_state:
                self.run_update_world_state()
                
            if self.player_message_is_instruction:
                self.player_message.hide()
                TM.game_state.set_var("instr.lastprocessed_call", self.player_message.id, commit=False)
                TM.emit_status("success", MSG_PROCESSED_INSTRUCTIONS, as_scene_message=True)
                
            elif self.player_message and not TM.game_state.has_var("instr.has_issued_instructions"):
                # simulation started, player message is NOT an instruction, and player has not given
                # any instructions
                self.guide_player()

            elif self.player_message and not TM.scene.npc_character_names():
                # simulation started, player message is NOT an instruction, but there are no npcs to interact with 
                self.narrate_round()
         
        def guide_player(self):
            TM.agents.narrator.action_to_narration(
                action_name="paraphrase",
                narration=MSG_HELP,
                emit_message=True
            )
                
        def narrate_round(self):
            TM.agents.narrator.action_to_narration(
                action_name="progress_story",
                narrative_direction=PROMPT_NARRATE_ROUND,
                emit_message=True
            )
            
        def run_update_world_state(self, force=False):
            TM.log.debug("SIMULATION SUITE: update world state", force=force)
            TM.emit_status("busy", "Simulation suite updating world state.", as_scene_message=True)
            TM.agents.world_state.update_world_state(force=force)
            TM.emit_status("success", "Simulation suite updated world state.", as_scene_message=True)
            
    SimulationSuite().run()